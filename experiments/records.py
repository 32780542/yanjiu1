"""Append-only run directories and explicit failure states, including interrupts."""
from datetime import datetime,timezone
import json
import os
import traceback
from uuid import uuid4
from research.common import output_path


def atomic_json(path,data):
    path=output_path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.writing')
    temporary.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    os.replace(temporary,path)


class RunRecord:
    def __init__(self,base,metadata):
        self.base=output_path(base)
        self.run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'_'+uuid4().hex[:8]
        self.path=self.base/self.run_id
        self.metadata=metadata
        self.finished=False

    def __enter__(self):
        self.path.mkdir(parents=True,exist_ok=False)
        self._save({'passed':False,'status':'running'})
        try:
            atomic_json(self.path/'metadata.json',{**self.metadata,'run_id':self.run_id})
        except BaseException as exc:
            self.__exit__(type(exc),exc,exc.__traceback__)
            raise
        return self

    def _save(self,result):
        atomic_json(self.path/'validation.json',{**result,'run_id':self.run_id})
        atomic_json(self.base/'latest.json',{'run_id':self.run_id,'path':str(self.path),
                                          'status':result['status'],'passed':result['passed']})

    def finish(self,result):
        self._save({**result,'status':'completed'})
        self.finished=True

    def __exit__(self,kind,error,tb):
        if error is not None:
            self._save({'passed':False,'status':'failed','error':f'{kind.__name__}: {error}',
                        'traceback':''.join(traceback.format_exception(kind,error,tb))})
        elif not self.finished:
            self._save({'passed':False,'status':'failed','error':'Run not finalized'})
            raise RuntimeError('Run not finalized')
        return False
