import os,json,re,urllib.request,urllib.parse
from concurrent.futures import ThreadPoolExecutor
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
def request(url):
 return urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Cache-Control':'no-cache','Accept':'*/*'})
def get(url):
 with urllib.request.urlopen(request(url),timeout=25) as r:
  p=Page(); p.raw=r.read().decode('utf-8','replace'); p.feed(p.raw); return r.geturl(),p
colors={'Black':'JJ7604-001','Gradient Camo':'JJ7603-900','White':'JJ7602-100'}
path=Path('state.json')
old=json.loads(path.read_text()) if path.exists() else {}
new={}; events=[]
store='https://shop.travisscott.com/'
shoe_rx=re.compile(r'air[ -]*force[ -]*1|\baf[ -]*1\b|JJ760[234]|gradient[ -]*camo',re.I)
raffle_rx=re.compile(r'raffle|enter[ -]*(?:the[ -]*)?draw|sweepstakes',re.I)
def json_get(url):
 with urllib.request.urlopen(request(url),timeout=15) as r:
  return json.load(r)
def catalog():
 data=json_get(store+'products.json?limit=250')
 if not isinstance(data.get('products'),list): raise ValueError('Missing products list')
 result={}
 for p in data['products']:
  variants=p.get('variants',[])
  identity=' '.join([str(p.get('title','')),str(p.get('handle',''))]+[str(v.get('sku','')) for v in variants])
  if not shoe_rx.search(identity): continue
  url=store+'products/'+str(p['handle'])
  result[url]={'title':p.get('title'),'variants':[{k:v.get(k) for k in ('id','title','sku','available','price')} for v in variants]}
 return result

def raw_signals(raw):
 return {'raffle_states':sorted(set(re.findall(r'"raffleStatus"\s*:\s*"([^"]+)"',raw,re.I))),
 'available':sorted(set(re.findall(r'"id"\s*:\s*(\d+)[^{}]*?"sku"\s*:\s*"(JJ760[234]-\d+)"[^{}]*?"available"\s*:\s*true',raw,re.I))),
 'handles':sorted(set(re.findall(r'"handle"\s*:\s*"([^"]*(?:air-force-1|af1|gradient-camo)[^"]*)"',raw,re.I)))}
for url in ['https://www.cactusjack.com/','https://shop.travisscott.com/']:
 try:
  final,p=get(url); s=' '.join(' '.join(p.words).split())
  snap={'url':final,'password':p.password or '/password' in final,'raffle':bool(re.search(r'enter (?:the )?(?:raffle|draw)',s,re.I)),'shoes':{}}
  for name,sku in colors.items():
   matches=list(re.finditer(r'(?i)(?:'+re.escape(sku)+r'|'+re.escape(name)+r')',s))
   snippets=[s[max(0,m.start()-100):m.end()+100] for m in matches]
   relevant=[x for x in snippets if re.search(r'air force|af1|sneaker|'+sku,x,re.I)]
   snap['shoes'][name]=sorted(set(relevant))
  snap['links']=sorted(set(urllib.parse.urljoin(final,x) for x in p.links if re.search(r'air.force|af1|raffle|JJ760[234]|gradient.camo|sweepstakes|enter.draw',x,re.I)))
  snap['raw_signals']=raw_signals(p.raw)
  if snap['raw_signals']['raffle_states']:
   snap['raffle']=any(x.lower() in ('open','live','active','started') for x in snap['raw_signals']['raffle_states'])
  new[url]=snap
  previous=old.get(url,{})
  comparable=snap if 'raw_signals' in previous else {k:v for k,v in snap.items() if k!='raw_signals'}
  if previous and (previous!=comparable or ('raw_signals' not in previous and (snap['raffle'] or snap['raw_signals']['available']))): events.append(url)
  if url not in old and (snap['raffle'] or snap['password']): events.append(url)
 except Exception as e: print(url,e)
if not new: raise SystemExit('No successful homepage checks')
# Public catalog may be disabled; never interpret an unavailable endpoint as out of stock.
try:
 products=catalog()
 new['_catalog']=products
 if products and old.get('_catalog')!=products:
  events.extend(products.keys())
 elif '_catalog' in old and old['_catalog']!=products:
  events.append(store+'products.json')
 print('Public catalog available; matching products:',len(products))
except Exception as e: print('Public catalog unavailable:',type(e).__name__)
# Watch public product pages if the storefront or catalog exposes a matching link.
links={store+'products/'+h for h in ('air-force-1-07-rs-black-placeholder','air-force-1-07-rs-gradient-camo-placeholder','air-force-1-07-rs-white-copy')}
for snap in list(new.values()):
 if isinstance(snap,dict) and 'links' in snap:
  links.update(snap['links'])
links.update(new.get('_catalog',{}))
links.update(old.get('_catalog',{}))
links.update(old.get('_product_pages',{}))
product_pages=dict(old.get('_product_pages',{}))
def product_page(url):
 parsed=urllib.parse.urlsplit(url)
 if parsed.hostname not in ('shop.travisscott.com','www.cactusjack.com','cactusjack.com') or '/products/' not in parsed.path: return None
 try:
  final,p=get(url)
  words=' '.join(' '.join(p.words).split())
  relevant=bool(shoe_rx.search(words) or shoe_rx.search(p.raw))
  statuses=sorted(set(re.findall(r'add to (?:cart|bag)|sold out|coming soon|enter (?:the )?(?:raffle|draw)|notify me|buy now|out of stock',words,re.I)))
  return url,{'url':final,'password':p.password,'relevant':relevant,'status':statuses,'raw_signals':raw_signals(p.raw)}
 except Exception: return None
with ThreadPoolExecutor(max_workers=4) as pool:
 for entry in pool.map(product_page,sorted(links)[:12]):
  if entry:
   url,snap=entry
   if snap.get('relevant') and ((url in product_pages and product_pages[url]!=snap) or snap['raw_signals']['available']): events.append(url)
   product_pages[url]=snap
if product_pages: new['_product_pages']=product_pages
print(json.dumps(new,indent=2))
if events:
 msg='Possible Cactus Jack sneaker change. Check immediately: '+ ' '.join(dict.fromkeys(events))
 target=store
 topic=os.environ.get('NTFY_TOPIC','')
 bark=os.environ.get('BARK_KEY','')
 sent=False
 if bark:
  try:
   payload={'device_key':bark,'title':'Travis Scott x GTA 6 AF1 | Site change','body':msg,'level':'timeSensitive','sound':'alarm','group':'Travis Scott x GTA 6 AF1','url':target}
   req=urllib.request.Request('https://api.day.app/push',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
   with urllib.request.urlopen(req,timeout=15) as r:
    if json.load(r).get('code')!=200: raise RuntimeError('Bark rejected push')
    print('Bark push accepted'); sent=True
  except Exception: print('Bark push failed')
 if topic:
  try:
   req=urllib.request.Request('https://ntfy.sh/'+urllib.parse.quote(topic,safe=''),data=msg.encode(),headers={'Title':'Travis Scott x GTA 6 AF1 | Site change','Priority':'urgent','Click':target})
   with urllib.request.urlopen(req,timeout=15) as r: print('ntfy push accepted',r.status); sent=True
  except Exception: print('ntfy push failed')
 if not sent: raise SystemExit('No notification channel accepted alert; retry next run')
old.update(new); path.write_text(json.dumps(old,sort_keys=True,indent=2)+'\n')
