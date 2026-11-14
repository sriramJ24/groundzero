import re,sys,subprocess
u=sys.argv[1]
t=subprocess.run(['curl','-sL',u],capture_output=True,text=True).stdout
for m in re.finditer(r'<tr>(.*?)</tr>',t,flags=re.S):
    r=m.group(1)
    h=re.findall(r'href="([^"]+)"',r); n=re.findall(r'>([^<>]+)</a>',r)
    if h and n and 'DOI/' in h[0]:
        print(n[0].strip(), '|', (n[1].strip() if len(n)>1 else ''), '|', h[0].split('DOI/640d826b-3fe8-4c3d-b84b-18a58900d315/')[1])
