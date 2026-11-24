import os,json,re,urllib.request,urllib.parse
from html.parser import HTMLParser
from pathlib import Path
class Page(HTMLParser):
 def __init__(self):
  super().__init__(); self.words=[]; self.links=[]; self.skip=0; self.password=False
 def handle_starttag(self,t,a):
  a=dict(a)
  if t in ('script','style'): self.skip+=1
  if t=='a' and 'href' in a: self.links.append(a['href'])
  if t=='input' and a.get('type')=='password': self.password=True
 def handle_endtag(self,t):
  if t in ('script','style'): self.skip=max(0,self.skip-1)
 def handle_data(self,d):
  if not self.skip: self.words.append(d)
def get(url):
 with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=25) as r:
  p=Page(); p.feed(r.read().decode('utf-8','replace')); return r.geturl(),p
colors={'Gradient Camo':'JJ7603-900','Black':'JJ7604-001','White':'JJ7602-100'}
path=Path('state.json')
old=json.loads(path.read_text()) if path.exists() else {}
new={}; events=[]
for url in ['https://www.cactusjack.com/','https://shop.travisscott.com/']:
 try:
  final,p=get(url); s=' '.join(' '.join(p.words).split())
  snap={'url':final,'password':p.password or '/password' in final,'raffle':bool(re.search(r'enter (?:the )?(?:raffle|draw)',s,re.I)),'shoes':{}}
  for name,sku in colors.items():
   matches=list(re.finditer(r'(?i)(?:'+re.escape(sku)+r'|'+re.escape(name)+r')',s))
   snippets=[s[max(0,m.start()-100):m.end()+100] for m in matches]
   relevant=[x for x in snippets if re.search(r'air force|af1|sneaker|'+sku,x,re.I)]
   snap['shoes'][name]=sorted(set(relevant))
  snap['links']=sorted(set(urllib.parse.urljoin(final,x) for x in p.links if re.search(r'air.force|af1|raffle|JJ760[234]',x,re.I)))
  new[url]=snap
  if url in old and old[url]!=snap: events.append(url)
  if url not in old and (snap['raffle'] or snap['password']): events.append(url)
 except Exception as e: print(url,e)
if not new: raise SystemExit('No successful checks')
print(json.dumps(new,indent=2))
if events:
 msg='Possible Cactus Jack sneaker change. Verify all three colors: '+ ' '.join(events)
 topic=os.environ.get('NTFY_TOPIC','')
 bark=os.environ.get('BARK_KEY','')
 sent=False
 if bark:
  try:
   payload={'device_key':bark,'title':'GTA 6 AF1 storefront change','body':msg,'level':'timeSensitive','sound':'alarm','group':'GTA 6 AF1','url':'https://shop.travisscott.com/'}
   req=urllib.request.Request('https://api.day.app/push',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
   with urllib.request.urlopen(req,timeout=15) as r:
    if json.load(r).get('code')!=200: raise RuntimeError('Bark rejected push')
    print('Bark push accepted'); sent=True
  except Exception: print('Bark push failed')
 if topic:
  try:
   req=urllib.request.Request('https://ntfy.sh/'+urllib.parse.quote(topic,safe=''),data=msg.encode(),headers={'Title':'GTA 6 AF1 storefront change','Priority':'urgent','Click':'https://shop.travisscott.com/'})
   with urllib.request.urlopen(req,timeout=15) as r: print('ntfy push accepted',r.status); sent=True
  except Exception: print('ntfy push failed')
 if not sent: raise SystemExit('No notification channel accepted alert; retry next run')
old.update(new); path.write_text(json.dumps(old,sort_keys=True,indent=2)+'\n')
