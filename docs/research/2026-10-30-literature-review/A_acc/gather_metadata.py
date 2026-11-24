import requests, concurrent.futures, json, re, time
from pathlib import Path
BASE=Path(__file__).parent
TITLES=[
'String stability of interconnected systems',
'Constant Spacing Strategies for Platooning in Automated Highway Systems',
'Intelligent cruise control systems and traffic flow stability',
'Optimal Adaptive Cruise Control with Guaranteed String Stability',
'String Stability Analysis of Adaptive Cruise Controlled Vehicles',
'Practical String Stability of Platoon of Adaptive Cruise Control Vehicles',
'String Stability Conditions of Adaptive Cruise Control Algorithms',
'Disturbance Propagation in Vehicle Strings',
'String Instability in Classes of Linear Time Invariant Formation Control With Limited Communication Range',
'Are Commercially Implemented Adaptive Cruise Control Systems String Stable?',
'Model based string stability of adaptive cruise control systems using field data',
'Impacts of commercially available adaptive cruise control vehicles on highway stability and throughput',
'Empirical Study on the Properties of Adaptive Cruise Control Systems and Their Impact on Traffic Flow and String Stability',
'A study on the response time of Adaptive Cruise Control systems',
'An open database of car-following experiments to study the properties of commercial ACC systems',
'Requiem on the positive effects of commercial adaptive cruise control on motorway traffic and recommendations for future automated driving systems',
'Fundamental diagrams of commercial adaptive cruise control: Worldwide experimental evidence',
'Car-Following Properties of a Commercial Adaptive Cruise Control System',
'Driving characteristics and adaptive cruise control',
'Significance of low-level control to string stability under adaptive cruise control: Algorithms, theory and experiments',
'Impact of acceleration/deceleration limits on the string stability of adaptive cruise control',
'Multianticipation for string stable Adaptive Cruise Control and increased motorway capacity without vehicle-to-vehicle communication',
'Experimental investigation of the multianticipation mechanism in commercial SAE level 2 automated driving vehicles and associated safety impact',
'Delays, inaccuracies and anticipation in microscopic traffic models',
'Influence of Reaction Times and Anticipation on Stability of Vehicular Traffic Flow',
'A multi-anticipative car-following model',
'Congested traffic states in empirical observations and microscopic simulations',
'Enhanced intelligent driver model to access the impact of driving strategies on traffic capacity',
'Jam-Avoiding Adaptive Cruise Control (ACC) and its Impact on Traffic Dynamics',
'Extending adaptive cruise control to adaptive driving strategies',
'Stabilizing traffic flow via autonomous vehicles: A linear perturbation analysis in the presence of heterogeneous time delays',
'Stability of heterogeneous traffic with reaction delays',
'A general car-following model with explicit reaction times',
'A full velocity difference car-following model based on the car-following theory',
'Dynamical model of traffic congestion and numerical simulation',
'A behavioural car-following model for computer simulation',
'Stability analysis of a heterogeneous platoon with time-varying delays',
'Heterogeneous string stability of unidirectionally interconnected cascaded systems',
'String stability of heterogeneous vehicle platoons',
'A comparison of spacing and headway control laws for automatically controlled vehicles',
'Safe and comfortable driving of autonomous vehicles with nonlinear ACC controllers',
'A Nonlinear CTH-Based Adaptive Cruise Controller With Safety and String Stability Guarantees',
'Driving towards stability and efficiency: A variable time gap strategy for Adaptive Cruise Control',
'String Stability Analysis and Design Guidelines for PD Controllers in Adaptive Cruise Control Systems',
'Controlling Congestion in Traffic Flow with a Single Autonomous Vehicle',
'Dissipation of stop-and-go waves via control of autonomous vehicles: Field experiments',
'Stabilizing vehicular platoons using adaptive cruise control',
'The impact of cooperative adaptive cruise control on traffic-flow characteristics',
'Modeling cooperative and autonomous adaptive cruise control dynamic responses using experimental data',
'A review of constant time headway policy for automatic vehicle following',
'On the string stability of car following models with anticipation',
'Understanding widely scattered traffic flows, the capacity drop, platoons, and times-to-collision as effects of variance-driven time gaps',
]
def clean(s): return re.sub('<[^>]+>',' ',s or '').replace('\n',' ').strip()
def get(q):
 try:
  r=requests.get('https://api.crossref.org/works',params={'query.title':q,'rows':2},headers={'User-Agent':'ResearchReview/1.0'},timeout=40)
  r.raise_for_status()
  out=[]
  for x in r.json()['message']['items']:
   out.append({'title':x.get('title',[''])[0],'doi':x.get('DOI'),'authors':[(' '.join([a.get('given',''),a.get('family','')])).strip() for a in x.get('author',[])], 'year':(x.get('published-print',x.get('published',{})).get('date-parts',[[None]])[0][0]),'url':x.get('URL'),'abstract':clean(x.get('abstract','')),'publisher':x.get('publisher'),'links':x.get('link',[]),'score':x.get('score')})
  return {'query':q,'matches':out}
 except Exception as e:return {'query':q,'error':str(e)}
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex: data=list(ex.map(get,TITLES))
(BASE/'metadata_candidates.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
for i,x in enumerate(data,1):
 m=x.get('matches',[{}])[0]
 print(i,m.get('year'),m.get('title'),m.get('doi'),'ABSTRACT' if m.get('abstract') else '')
