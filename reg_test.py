import asyncio, json, random, string, sys, urllib.request, urllib.parse, traceback, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import subprocess

REPORT_URL = 'http://23.148.228.38:8001/report'

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

async def select_country(pg):
    """de_DE Step2: 选择 Land/Region = Österreich"""
    labels = ["austria", "österreich", "奥地利"]
    try:
        for sel in ["select[name='country']", "select#country", "#Signup-CountryField select", "select[data-qa='country']", "select"]:
            try:
                el = await pg.query_selector(sel)
                if not el:
                    continue
                opts = await el.query_selector_all("option")
                if not opts:
                    continue
                for opt in opts:
                    text = (await opt.inner_text()).strip()
                    if text.lower() in labels or "at" in text.lower():
                        await el.select_option(label=text)
                        print('COUNTRY_SELECT', text, flush=True)
                        return True
            except Exception:
                continue
    except Exception:
        pass
    for csel in [
        "[aria-label*='Land/Region']", "[aria-label*='Country']",
        "button:has-text('Land/Region')", "button:has-text('Country')",
        "#Signup-CountryField", "input[aria-label*='Land']", "input[aria-label*='Country']",
    ]:
        try:
            el = await pg.query_selector(csel)
            if el and await el.is_visible():
                await el.click()
                await pg.wait_for_timeout(1200)
                for opt in ["text=Österreich", "text=Austria", "text=ÖSTERREICH"]:
                    try:
                        await pg.click(opt, timeout=4000)
                        print('COUNTRY_SELECT', opt, flush=True)
                        return True
                    except Exception:
                        continue
        except Exception:
            continue
    print('COUNTRY_SELECT_FAIL', flush=True)
    return False

async def fill_step2(pg):
    for sel in ["input[autocomplete='given-name']",'#Signup-FirstNameField',"input[name='firstName']"]:
        try: await pg.fill(sel,'Kundby'); break
        except Exception: pass
    for sel in ["input[autocomplete='family-name']",'#Signup-LastNameField',"input[name='lastName']"]:
        try: await pg.fill(sel,'Olivela'); break
        except Exception: pass
    for sel in ["input[autocomplete='bday-year']",'#Signup-DateOfBirthChooser-Year',"input[name='year']"]:
        try: await pg.fill(sel,'1995'); break
        except Exception: pass
    for msel in ['#Signup-DateOfBirthChooser-Month',"button[name='month']"]:
        try:
            el = await pg.query_selector(msel)
            if el and await el.is_visible():
                await el.click(); await pg.wait_for_timeout(800)
                for _ in range(3):
                    await pg.keyboard.press('ArrowDown'); await pg.wait_for_timeout(80)
                await pg.keyboard.press('Enter')
                break
        except Exception: pass
    await pg.wait_for_timeout(800)
    await select_country(pg)
    await pg.wait_for_timeout(800)

async def try_step1(pg, em):
    """填邮箱密码点Weiter, 返回 True 表示进入Step2"""
    await pg.fill('#Signup-EmailField', em)
    await pg.fill('#Signup-PasswordField', 'Abcd1234!xyz')
    await pg.click("button:has-text('Weiter')")
    await pg.wait_for_timeout(12000)
    txt = await pg.evaluate('document.body.innerText.slice(0,400)')
    return ('Schritt 2' in txt) or ('Vorname' in txt), txt

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
    report({'stage':'started','n': n, **info})
    em = f'{rn(7)}.{rn(8)}.awsapps.com@{rn(4)}.{rn(4)}.{random.choice(["es","edu","jp"])}'
    print('EMAIL', em, flush=True)
    try:
        from playwright.async_api import async_playwright
        URL = build_url()
        async with async_playwright() as p:
            b = await p.chromium.launch(headless=True, args=['--no-sandbox','--disable-dev-shm-usage'])
            report({'stage':'browser_ok','n': n, **info})
            ctx = await b.new_context(locale='de-DE', timezone_id='Europe/Vienna')
            pg = await ctx.new_page()
            await pg.goto(URL, wait_until='domcontentloaded', timeout=90000)
            await pg.wait_for_timeout(10000)
            ok, txt = await try_step1(pg, em)
            if not ok:
                print('STEP1_RETRY', flush=True)
                report({'stage':'step1_retry','email':em,'body':txt[:200],'n': n, **info})
                em2 = f'{rn(7)}.{rn(8)}.awsapps.com@{rn(4)}.{rn(4)}.{random.choice(["es","edu","jp"])}'
                await pg.goto(URL, wait_until='domcontentloaded', timeout=90000)
                await pg.wait_for_timeout(8000)
                ok, txt = await try_step1(pg, em2)
                if not ok:
                    err = 'unknown'
                    for k in ['ungültig','Tippfehler','bereits','Fehler','robot']:
                        if k in txt: err = k; break
                    print('STEP1_FAIL', err, flush=True)
                    report({'stage':'step1_fail','err':err,'email':em,'email2':em2,'body':txt[:200],'n': n, **info})
                    await b.close(); return
                em = em2
            print('STEP2_OK', flush=True)
            report({'stage':'step2_ok','email':em,'n': n, **info})
            await fill_step2(pg)
            clicked = False
            for btn in ["button:has-text('Konto erstellen')","button:has-text('Create account')","button[type='submit']"]:
                try:
                    el = await pg.query_selector(btn)
                    if el and await el.is_visible():
                        await el.click(); clicked = True; print('CREATE_CLICKED', flush=True); break
                except Exception: pass
            if not clicked:
                report({'stage':'create_btn_not_found','email':em,'n': n, **info})
            await pg.wait_for_timeout(15000)
            url = pg.url[:120]
            body = await pg.evaluate('document.body.innerText.slice(0,400)')
            print('URL', url, flush=True)
            print('BODY', body[:250].replace(chr(10),' | '), flush=True)
            if '#/signup/2' in url or 'Schritt 2' in body or 'Vorname' in body:
                err = 'unknown'
                for k in ['ungültig','Tippfehler','bereits','Fehler','robot','not available','nicht']:
                    if k in body: err = k; break
                print('STEP2_FAIL', err, flush=True)
                report({'stage':'step2_fail','err':err,'email':em,'body':body[:200],'n': n, **info})
                await b.close(); return
            for _ in range(30):
                await asyncio.sleep(2)
                cookies = await ctx.cookies()
                names = [c['name'] for c in cookies if c.get('value')]
                if 'ims_sid' in names and 'aux_sid' in names:
                    print('SUCCESS_LOGIN_COOKIE', flush=True)
                    report({'stage':'success','email':em,'url':url,'n': n, **info})
                    await b.close(); return
            print('NO_COOKIE', flush=True)
            report({'stage':'no_cookie','email':em,'url':url,'body':body[:200],'n': n, **info})
            await b.close()
    except Exception as e:
        report({'stage':'exception','err':str(e)[:200],'n': n, **info})
        traceback.print_exc()

asyncio.run(main())
