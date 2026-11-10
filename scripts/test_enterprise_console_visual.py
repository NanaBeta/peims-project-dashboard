"""Offline visual behavior smoke test, fully fabricated API responses."""
from pathlib import Path
import json
from playwright.sync_api import sync_playwright

root=Path(__file__).resolve().parents[1]/'enterprise'/'console_assets'
html=(root/'index.html').read_text();css=(root/'console.css').read_text();js=(root/'console.js').read_text()
project={'id':'P1','title':'Electrical Substation Modernization','currency':'GHS','role':'manager'}
tasks=[{'id':str(i),'project_id':'P1','reference':f'EL-{i:03}','title':name,'description':'Design and commissioning package for infrastructure projects','kind':'task','parent_id':None,'status':status,'priority':'high','assigned_sub':'eng','start_date':'2026-11-04','due_date':due,'estimate_hours':'8.00','progress_pct':pct,'version':1,'created_by':'mgr','updated_by':'mgr'} for i,(name,status,due,pct) in enumerate([
('Design relay protection scheme','in_progress','2026-11-15','40.00'),('Inspect switchgear delivery','blocked','2026-11-11','10.00'),('Review electrical drawings','todo','2026-11-20','0'),('Test commissioning procedures','done','2026-11-09','100.00')],1)]
api={'/console/api/session':{'subject':'mgr','csrf':'test-csrf','projects':[project]},'/console/api/projects/P1/summary':{'total':4,'open':3,'overdue':1,'milestones':0},'/console/api/projects/P1/tasks':tasks}


prelude = """
window.fetch = async function(url) {
  const key = String(url).split('?')[0];
  const response = globalThis.__fake_api[key] || (key.startsWith('/console/api/projects/P1/tasks/') ? globalThis.__fake_tasks.find(t=>t.id===key.split('/').pop()) : null);
  return new Response(JSON.stringify(response || []),{status:200,headers:{'Content-Type':'application/json'}});
};
"""
mock_data={**api, **{f'/console/api/projects/P1/tasks/{t["id"]}':t for t in tasks}}

with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
    for width,height in ((1440,920),(768,960),(390,844)):
        page=b.new_page(viewport={'width':width,'height':height},device_scale_factor=1)
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.set_content(html.replace('<link rel="stylesheet" href="/console/assets/console.css">','').replace('<script src="/console/assets/console.js" defer></script>',''))
        page.add_style_tag(content=css)
        page.evaluate('globalThis.__fake_api = '+json.dumps(mock_data))
        page.evaluate('globalThis.__fake_tasks = '+json.dumps(tasks))
        page.add_script_tag(content=prelude+js)
        page.wait_for_selector('#app:not([hidden])')
        assert not page.locator('#login').is_visible()
        assert page.locator('#heroOpen').inner_text()=='3'
        assert page.locator('#attention .list-row').count()==2
        page.locator('#openTasks').click()
        assert page.locator('#tasksPage').is_visible()
        assert page.locator('.task-card').count()==4
        for view in ('list','timeline','calendar','board'):
            page.locator(f'[data-view="{view}"]').click()
            if view=='list':assert page.locator('.data-table tbody tr').count()==4
            if view=='timeline':assert page.locator('.timeline-bar').count()==4
            if view=='calendar':assert page.locator('.calendar-day').count()>=28
        page.locator('.task-card').first.click()
        page.wait_for_selector('#detailDialog[open]')
        assert page.locator('#detailHeading').inner_text()
        page.locator('[data-close="detailDialog"]').click()
        assert not page.locator('#detailDialog').is_visible()
        page.locator('[data-page="home"]').click()
        assert page.locator('#homePage').is_visible()
        page.screenshot(path=f'/mnt/data/PEIMS_v081_QA_{width}.png',full_page=True)
        overflow=page.evaluate('document.documentElement.scrollWidth > window.innerWidth + 1')
        assert not overflow,f'Unexpected horizontal overflow at {width}px'
        assert not errors,(width,errors)
        print('PASS visual+interaction width:',width)
        page.close()
    b.close()
