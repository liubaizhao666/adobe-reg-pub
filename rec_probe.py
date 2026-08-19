import asyncio, json, random, string, sys, urllib.request, urllib.parse, traceback, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import subprocess

REPORT_URL = 'http://23.148.228.38:8001/report'
SITEKEY = '6LcGE-4ZAAAAAG2tFdbr7QqpimWAPqhLjI8_O_69'

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

def rn(n): return ''.join(random.choices(string.ascii_lowercase, k=n))

def build_url():
    relay = '5f63be8b-2d0d-4c9c-ac94-09add7650fde'
    state = json.dumps({"name":"AccessTokenFlow","side":"popup","data":{"access_token":"","returnOrigin":"https://auth-light.identity.adobe.com","client_id":"projectx_webapp","clientId":"projectx_webapp","relay":relay,"useMessageChannel":True}}, separators=(",",":"))
    se = urllib.parse.quote(state)
    cb = f'https://ims-na1.adobelogin.com/ims/adobeid/projectx_webapp/AdobeID/token?redirect_uri=https%3A%2F%2Fauth-light.identity.adobe.com%2Fwrapper-popup-helper%2Findex.html&state={se}&code_challenge_method=plain&use_ms_for_expiry=false'
    scope = 'AdobeID,firefly_api,openid'
    return (f'https://auth.services.adobe.com/de_DE/deeplink.html?deeplink=signup&callback={urllib.parse.quote(cb,safe="")}&client_id=projectx_webapp&scope={urllib.parse.quote(scope,safe="")}&state={se}&relay={relay}&locale=de_DE&flow_type=token&idp_flow_type=create_account&dl=true&s_p=google%2Cfacebook%2Capple%2Cmicrosoft%2Cline%2Ckakao&response_type=token&code_challenge_method=plain&redirect_uri=https%3A%2F%2Fauth-light.identity.adobe.com%2Fwrapper-popup-helper%2Findex.html&use_ms_for_expiry=false#/signup')

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
    report({'stage':'rec_started','n': n, **info})
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            b = await p.chromium.launch(headless=True, args=['--no-sandbox','--disable-dev-shm-usage'])
            ctx = await b.new_context(locale='de-DE', timezone_id='Europe/Vienna',
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36')
            pg = await ctx.new_page()
            reqs = []
            pg.on('request', lambda r: reqs.append(r.url[:200]))
            URL = build_url()
            await pg.goto(URL, wait_until='domcontentloaded', timeout=90000)
            await pg.wait_for_timeout(10000)
            frames_info = await pg.evaluate('''() => {
                const frames = [...document.querySelectorAll('iframe')].map(f => (f.src||'').slice(0,200));
                const scripts = [...document.querySelectorAll('script')].map(s => (s.src||'').slice(0,200)).filter(s => s);
                return {frames, scripts};
            }''')
            report({'stage':'rec_frames','frames':frames_info,'n': n, **info})
            em = f'{rn(7)}.{rn(8)}.awsapps.com@{rn(4)}.{rn(4)}.{random.choice(["es","edu","jp"])}'
            await pg.fill('#Signup-EmailField', em)
            await pg.fill('#Signup-PasswordField', 'Abcd1234!xyz')
            await pg.click("button:has-text('Weiter')")
            await pg.wait_for_timeout(10000)
            frames2 = await pg.evaluate('''() => {
                const frames = [...document.querySelectorAll('iframe')].map(f => (f.src||'').slice(0,200));
                const rec = {g: typeof window.grecaptcha,
                    scripts: [...document.querySelectorAll('script')].map(s => (s.src||'')).filter(s => s.includes('recaptcha') || s.includes('google'))};
                return {frames, rec};
            }''')
            report({'stage':'rec_after_step1','frames2':frames2,'n': n, **info})
            hit = [u for u in reqs if any(k in u for k in ['recaptcha','bfp','google.com','signin','gstatic','accounts.adobe'])]
            report({'stage':'rec_reqs','reqs':hit[:30],'n': n, **info})
            await b.close()
    except Exception as e:
        report({'stage':'rec_exception','err':str(e)[:200],'n': n, **info})
        traceback.print_exc()

asyncio.run(main())
