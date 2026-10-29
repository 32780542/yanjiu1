"""Run one command with durable separate logs, bounded time, and a compact result.

Usage: python -I -B -S scripts/run_logged.py --label controller --timeout 120 --
       python -I -B -S run.py test
Every invocation allocates a new directory; a failed attempt is never reused.

Windows requires CPython. The target is created suspended, assigned to a private
Job Object, then resumed. Ordinary child processes cannot break away. Work
delegated through external services (for example WMI) is outside this ownership.
An OS-level kill of this runner between CreateProcess and Job assignment can
leave a suspended target; normal Python exceptions in that window clean it up.
After assignment, closing the runner's sole Job handle kills its entire Job.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def write_json(path, data):
    temporary = path.with_suffix(path.suffix+'.writing')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    os.replace(temporary, path)


def hash_file(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


class WindowsJobChild:
    """Own a suspended-created CPython/Windows child and its ordinary descendants."""

    def __init__(self, command, stdout, stderr):
        import _winapi
        import ctypes
        from ctypes import wintypes as wt
        import msvcrt

        self.api, self.ctypes = _winapi, ctypes
        self.command, self.returncode = command, None
        self.job = self.handle = self.thread = None
        self.pid = None
        kernel = self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)

        class BasicLimits(ctypes.Structure):
            _fields_ = [('PerProcessUserTimeLimit', ctypes.c_longlong),
                        ('PerJobUserTimeLimit', ctypes.c_longlong),
                        ('LimitFlags', wt.DWORD), ('MinimumWorkingSetSize', ctypes.c_size_t),
                        ('MaximumWorkingSetSize', ctypes.c_size_t),
                        ('ActiveProcessLimit', wt.DWORD), ('Affinity', ctypes.c_size_t),
                        ('PriorityClass', wt.DWORD), ('SchedulingClass', wt.DWORD)]

        class IoCounters(ctypes.Structure):
            _fields_ = [(name, ctypes.c_ulonglong) for name in
                        ('ReadOperationCount', 'WriteOperationCount', 'OtherOperationCount',
                         'ReadTransferCount', 'WriteTransferCount', 'OtherTransferCount')]

        class ExtendedLimits(ctypes.Structure):
            _fields_ = [('BasicLimitInformation', BasicLimits), ('IoInfo', IoCounters),
                        ('ProcessMemoryLimit', ctypes.c_size_t),
                        ('JobMemoryLimit', ctypes.c_size_t),
                        ('PeakProcessMemoryUsed', ctypes.c_size_t),
                        ('PeakJobMemoryUsed', ctypes.c_size_t)]

        class Accounting(ctypes.Structure):
            _fields_ = [(name, ctypes.c_longlong) for name in
                        ('TotalUserTime', 'TotalKernelTime', 'ThisPeriodTotalUserTime',
                         'ThisPeriodTotalKernelTime')] + [(name, wt.DWORD) for name in
                        ('TotalPageFaultCount', 'TotalProcesses', 'ActiveProcesses',
                         'TotalTerminatedProcesses')]

        self.Accounting = Accounting
        signatures = {
            'CreateJobObjectW': ([ctypes.c_void_p, wt.LPCWSTR], wt.HANDLE),
            'SetInformationJobObject': ([wt.HANDLE, ctypes.c_int, ctypes.c_void_p, wt.DWORD], wt.BOOL),
            'AssignProcessToJobObject': ([wt.HANDLE, wt.HANDLE], wt.BOOL),
            'TerminateJobObject': ([wt.HANDLE, wt.UINT], wt.BOOL),
            'QueryInformationJobObject': ([wt.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                           wt.DWORD, ctypes.c_void_p], wt.BOOL),
            'ResumeThread': ([wt.HANDLE], wt.DWORD),
        }
        for name, (arguments, result) in signatures.items():
            function = getattr(kernel, name)
            function.argtypes, function.restype = arguments, result

        try:
            self.job = self.check(kernel.CreateJobObjectW(None, None), 'CreateJobObjectW')
            limits = ExtendedLimits()
            limits.BasicLimitInformation.LimitFlags = 0x2000  # KILL_ON_JOB_CLOSE; no breakaway.
            self.check(kernel.SetInformationJobObject(self.job, 9, ctypes.byref(limits),
                                                      ctypes.sizeof(limits)),
                       'SetInformationJobObject')
            with open(os.devnull, 'rb') as stdin:
                handles = [msvcrt.get_osfhandle(stream.fileno())
                           for stream in (stdin, stdout, stderr)]
                original_inheritance = [os.get_handle_inheritable(handle) for handle in handles]
                startup = subprocess.STARTUPINFO()
                startup.dwFlags = subprocess.STARTF_USESTDHANDLES | subprocess.STARTF_USESHOWWINDOW
                startup.wShowWindow = subprocess.SW_HIDE
                startup.hStdInput, startup.hStdOutput, startup.hStdError = handles
                # Only these three handles are inherited, never the Job handle.
                startup.lpAttributeList = {'handle_list': handles}
                try:
                    for handle in handles:
                        os.set_handle_inheritable(handle, True)
                    self.handle, self.thread, self.pid, _ = _winapi.CreateProcess(
                        None, subprocess.list2cmdline(command), None, None, True,
                        0x4 | subprocess.CREATE_NO_WINDOW,  # CREATE_SUSPENDED
                        None, str(ROOT), startup)
                    self.check(kernel.AssignProcessToJobObject(self.job, self.handle),
                               'AssignProcessToJobObject')
                    if kernel.ResumeThread(self.thread) == 0xFFFFFFFF:
                        self.check(0, 'ResumeThread')
                finally:
                    for handle, inheritable in zip(handles, original_inheritance):
                        os.set_handle_inheritable(handle, inheritable)
            _winapi.CloseHandle(self.thread)
            self.thread = None
        except BaseException:
            # The target cannot execute before assignment. Fail closed on any setup error.
            try:
                if self.handle is not None:
                    _winapi.TerminateProcess(self.handle, 1)
                    _winapi.WaitForSingleObject(self.handle, 8000)
            finally:
                self.close()
            raise

    def check(self, value, operation):
        if not value:
            error = self.ctypes.WinError(self.ctypes.get_last_error())
            raise OSError(f'{operation}: {error}')
        return value

    def wait(self, timeout):
        if self.returncode is None:
            # Bounded slices allow Python to handle Ctrl+C even without a console child.
            deadline = time.monotonic() + timeout
            while True:
                remaining = deadline - time.monotonic()
                state = self.api.WaitForSingleObject(self.handle,
                                                    max(0, min(100, int(remaining * 1000))))
                if state == self.api.WAIT_OBJECT_0:
                    self.returncode = self.api.GetExitCodeProcess(self.handle)
                    break
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(self.command, timeout)
        return self.returncode

    def stop_tree(self):
        self.check(self.kernel.TerminateJobObject(self.job, 1), 'TerminateJobObject')
        self.wait(8)
        deadline = time.monotonic() + 8
        while True:
            accounting = self.Accounting()
            self.check(self.kernel.QueryInformationJobObject(
                self.job, 1, self.ctypes.byref(accounting), self.ctypes.sizeof(accounting), None),
                'QueryInformationJobObject')
            if not accounting.ActiveProcesses:
                return {'method': 'windows_job', 'confirmed': True, 'active_processes': 0}
            if time.monotonic() >= deadline:
                raise TimeoutError('Job still contains active processes after termination')
            time.sleep(0.01)

    def close(self):
        # Closing our private Job handle also kills descendants if cleanup raised.
        for attribute in ('job', 'thread', 'handle'):
            handle = getattr(self, attribute)
            if handle is not None:
                self.api.CloseHandle(handle)
                setattr(self, attribute, None)


def start_child(command, stdout, stderr):
    if os.name == 'nt':
        return WindowsJobChild(command, stdout, stderr)
    return subprocess.Popen(command, cwd=ROOT, stdin=subprocess.DEVNULL,
                            stdout=stdout, stderr=stderr, start_new_session=True)


def stop_child(process):
    if os.name == 'nt':
        try:
            return process.stop_tree()
        finally:
            process.close()
    import signal
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait(timeout=8)
    # POSIX descendants can create new sessions; do not claim Windows Job semantics.
    return {'method': 'posix_process_group', 'confirmed': False,
            'detail': 'SIGKILL sent to owned group; detached sessions are outside ownership'}


def seal_result(folder, metadata):
    """Save the execution result before reading logs; archival is fallible bookkeeping."""
    metadata.update(archive_status='pending', log_hashes={}, archive_errors={})
    try:
        write_json(folder/'result.json', metadata)
    except Exception as error:
        metadata.update(status='metadata_error', archive_status='skipped',
                        record_error=f'{type(error).__name__}: {error}',
                        returncode=metadata['returncode'] or 1)
        return
    for name in ('stdout.log', 'stderr.log'):
        try:
            metadata['log_hashes'][name] = hash_file(folder/name)
        except Exception as error:
            metadata['archive_errors'][name] = f'{type(error).__name__}: {error}'
    if metadata['archive_errors']:
        metadata.update(archive_status='failed', returncode=metadata['returncode'] or 1)
        if metadata['status'] not in ('runner_error', 'termination_error'):
            metadata['status'] = 'archive_error'
    else:
        metadata['archive_status'] = 'complete'
    try:
        write_json(folder/'result.json', metadata)
    except Exception as error:
        # The pre-archival record remains available if this atomic replacement fails.
        metadata.update(status='metadata_error', record_error=f'{type(error).__name__}: {error}',
                        returncode=metadata['returncode'] or 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--label', required=True)
    parser.add_argument('--timeout', type=float, default=120)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1]==['--'] else args.command
    if not command or not (0 < args.timeout <= 7200):
        parser.error('Require a command and timeout in (0,7200] seconds')
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', args.label):
        parser.error('Label must contain 1-64 letters, digits, underscores or hyphens')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    folder = ROOT/'results/operations'/f'{stamp}_{args.label}_{uuid4().hex[:8]}'
    folder.mkdir(parents=True, exist_ok=False)
    metadata = {'command':command, 'cwd':str(ROOT), 'timeout_s':args.timeout,
                'started_utc':datetime.now(timezone.utc).isoformat(), 'status':'starting',
                'python_version':sys.version, 'runner_executable':sys.executable,
                'tree_policy':'private_windows_job' if os.name=='nt' else 'posix_process_group'}
    process = None
    start = time.monotonic()
    code = 1
    try:
        write_json(folder/'started.json', metadata)
        # One read ties the saved wrapper source to its recorded hash.
        snapshot = Path(__file__).read_bytes()
        (folder/'runner_snapshot.py').write_bytes(snapshot)
        metadata['runner_sha256'] = hashlib.sha256(snapshot).hexdigest()
        with (folder/'stdout.log').open('wb') as stdout, (folder/'stderr.log').open('wb') as stderr:
            process = start_child(command, stdout, stderr)
            metadata.update(status='running', pid=process.pid)
            write_json(folder/'started.json', metadata)
            try:
                code = process.wait(timeout=args.timeout)
                metadata['status'] = 'completed' if code==0 else 'failed'
            except subprocess.TimeoutExpired:
                metadata['status'] = 'timeout'
                code = 124
    except KeyboardInterrupt:
        metadata['status'] = 'interrupted'
        code = 130
    except Exception as exc:
        metadata.update(status='runner_error', error=f'{type(exc).__name__}: {exc}')
        code = 1
    finally:
        metadata['execution_status'] = metadata['status']
        if process is not None:
            try:
                metadata['tree_cleanup'] = stop_child(process)
            except (Exception, KeyboardInterrupt) as cleanup:
                metadata['termination_error'] = f'{type(cleanup).__name__}: {cleanup}'
                metadata.update(status='termination_error',
                                tree_cleanup={'confirmed':False})
                code = code or 1
        metadata.update(returncode=code, child_returncode=process.returncode if process else None,
                        elapsed_s=round(time.monotonic()-start,3),
                        ended_utc=datetime.now(timezone.utc).isoformat())
        seal_result(folder, metadata)
    summary = {'status':metadata['status'], 'returncode':metadata['returncode'],
               'elapsed_s':metadata['elapsed_s'], 'path':str(folder)}
    if 'record_error' in metadata:
        summary['record_error'] = metadata['record_error'][:300]
    print(json.dumps(summary, ensure_ascii=True), flush=True)
    return metadata['returncode']


if __name__ == '__main__':
    raise SystemExit(main())
