import asyncio, json, random, string, sys, urllib.request, urllib.parse, traceback, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import subprocess

REPORT_URL = 'http://23.148.228.38:8001/report'
SITEKEY = '436DD567-5435-4B14-89A6-2F1188E11334'
CBNAME = 'setupEnforcementCompleteAccount'

def report(data):
    try:
        req = urllib.request.Request(REPORT_URL, data=json.dumps(data).encode(),
            headers={'Content-Type':'application/json'}, method='POST')
        urllib.request.urlopen(req, timeout=10)
        print('REPORTED', data.get('stage','?'), flush=True)
    except Exception as e:
        print('REPORT_ERR', str(e)[:150], flush=True)

def get_ip():
    try:
        return subprocess.check_output(['curl','-s','--max-time','8','https://ipinfo.io/json']).decode()
    except Exception:
        return '{}'

async def main():
    n = int(os.getenv('RUNNER_N', '1'))
    runner = os.getenv('RUNNER_NAME', '')
    info = {}
    try:
        j = json.loads(get_ip())
        info = {'ip': j.get('ip',''), 'cc': j.get('country',''), 'org': j.get('org','')}
    except Exception:
        pass
    info['runner'] = runner
    report({'stage':'a2_started','n': n, **info})
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            b = await p.chromium.launch(headless=True, args=['--no-sandbox','--disable-dev-shm-usage'])
            ctx = await b.new_context(locale='de-DE', timezone_id='Europe/Vienna',
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36')
            pg = await ctx.new_page()
            reqs = []
            pg.on('request', lambda r: reqs.append((r.method, r.url[:250])))
            await pg.goto('https://auth.services.adobe.com/de_DE/deeplink.html?deeplink=signup&locale=de_DE#/signup', wait_until='domcontentloaded', timeout=60000)
            await pg.wait_for_timeout(4000)
            await pg.evaluate('''(cbName) => {
                window.__ark_result = {};
                window[cbName] = function(enforcement) {
                    window.__ark_result.enforcement = true;
                    try {
                        enforcement.setConfig({
                            onCompleted: (resp) => {
                                window.__ark_result.done = true;
                                window.__ark_result.token = (resp && resp.token || '').slice(0,150);
                                window.__ark_result.resp = JSON.stringify(resp).slice(0,500);
                            },
                            onError: (e) => {
                                window.__ark_result.done = true;
                                window.__ark_result.error = JSON.stringify(e).slice(0,300);
                            },
                            onReady: () => { window.__ark_result.ready = true; },
                            onShown: () => { window.__ark_result.shown = true; }
                        });
                        enforcement.run();
                    } catch(e) { window.__ark_result.exc = String(e).slice(0,200); }
                };
            }''', CBNAME)
            await pg.evaluate('''([url, cb]) => {
                const s = document.createElement('script');
                s.src = url;
                s.setAttribute('data-callback', cb);
                s.async = true;
                s.defer = true;
                document.head.appendChild(s);
            }''', [f'https://adobe-api.arkoselabs.com/v2/{SITEKEY}/api.js', CBNAME])
            await pg.wait_for_timeout(3000)
            for _ in range(20):
                await asyncio.sleep(2)
                r = await pg.evaluate('window.__ark_result')
                if r.get('done') or r.get('exc'):
                    break
            r = await pg.evaluate('window.__ark_result')
            report({'stage':'a2_result','res':r,'n': n, **info})
            hit = [u for m,u in reqs if 'arkoselabs' in u or 'arks-client' in u or 'arkose' in u]
            report({'stage':'a2_reqs','reqs':hit[:25],'n': n, **info})
            await b.close()
    except Exception as e:
        report({'stage':'a2_exception','err':str(e)[:200],'n': n, **info})
        traceback.print_exc()

asyncio.run(main())
