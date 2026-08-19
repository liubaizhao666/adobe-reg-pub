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

async def set_react_input(pg, selector, value):
    try:
        return await pg.evaluate('''([sel, val]) => {
            const el = document.querySelector(sel);
            if (!el) return false;
            const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
            setter.call(el, val);
            el.dispatchEvent(new Event('input', {bubbles:true}));
            el.dispatchEvent(new Event('change', {bubbles:true}));
            return true;
        }''', [selector, value])
    except Exception as e:
        return False

async def force_select(pg, selector, value):
    """强制显示原生select并用Playwright真实选择"""
    try:
        sel = pg.locator(selector)
        await sel.evaluate("el => { el.style.display='block'; el.style.position='fixed'; el.style.top='0'; el.style.left='0'; el.style.zIndex='99999'; el.style.opacity='0.01'; }")
        await sel.select_option(value)
        return True
    except Exception as e:
        print('FORCE_SEL_ERR', str(e)[:80], flush=True)
        return False

async def pick_month(pg):
    """点击月份按钮并精确选择 März"""
    btn = await pg.query_selector('#Signup-DateOfBirthChooser-Month')
    if not btn:
        return 'no_btn'
    try:
        await btn.scroll_into_view_if_needed()
    except Exception:
        pass
    await btn.click()
    await pg.wait_for_timeout(1500)
    items = await pg.evaluate('''() => {
        const out = [];
        document.querySelectorAll('[role=option], li, [data-value], [role=menuitem]').forEach(e => {
            if (e.offsetParent !== null)
                out.push((e.getAttribute('data-value')||'') + ':' + (e.innerText||'').trim());
        });
        return JSON.stringify(out).slice(0, 400);
    }''')
    clicked = await pg.evaluate('''() => {
        const all = document.querySelectorAll('[role=option], li, [data-value], [role=menuitem]');
        for (const el of all) {
            if ((el.innerText||'').trim() === 'März' && el.offsetParent !== null) {
                el.click(); return true;
            }
        }
        return false;
    }''')
    if not clicked:
        await pg.keyboard.press('ArrowDown')
        await pg.keyboard.press('ArrowDown')
        await pg.keyboard.press('Enter')
        await pg.wait_for_timeout(400)
    await pg.wait_for_timeout(800)
    return 'clicked=' + str(clicked) + ' items=' + items

async def pick_country(pg):
    """选择国家 Österreich (fallback)"""
    btn = await pg.query_selector('#Signup-CountryChooser')
    if not btn:
        return 'no_btn'
    try:
        await btn.scroll_into_view_if_needed()
    except Exception:
        pass
    await btn.click()
    await pg.wait_for_timeout(1200)
    clicked = await pg.evaluate('''() => {
        const all = document.querySelectorAll('[role=option], li, [data-value], [role=menuitem]');
        for (const el of all) {
            if ((el.innerText||'').trim() === 'Österreich' && el.offsetParent !== null) {
                el.click(); return true;
            }
        }
        return false;
    }''')
    if not clicked:
        await pg.keyboard.press('Escape')
    await pg.wait_for_timeout(600)
    return 'clicked=' + str(clicked)

async def fill_step2(pg):
    """填 Step2 全部字段并返回状态"""
    for sel in ["input[autocomplete='given-name']",'#Signup-FirstNameField']:
        try: await pg.fill(sel,'Kundby'); break
        except Exception: pass
    for sel in ["input[autocomplete='family-name']",'#Signup-LastNameField']:
        try: await pg.fill(sel,'Olivela'); break
        except Exception: pass
    await set_react_input(pg, '#Signup-DateOfBirthChooser-Year', '1995')
    await pg.wait_for_timeout(500)
    m_res = await pick_month(pg)
    c_res = await pick_country(pg)
    await pg.wait_for_timeout(500)
    vals = await pg.evaluate('''() => ({
        monthBtn: (document.querySelector('#Signup-DateOfBirthChooser-Month')||{}).innerText||'',
        year: (document.querySelector('#Signup-DateOfBirthChooser-Year')||{}).value||'',
        ccBtn: (document.querySelector('#Signup-CountryChooser')||{}).innerText||''
    })''')
    return {'month': m_res, 'country': c_res, 'vals': vals}

async def get_form_errors(pg):
    try:
        return await pg.evaluate('''() => {
            const errs = [];
            document.querySelectorAll('[aria-invalid=true], [class*=error], [class*=invalid], [role=alert]').forEach(el => {
                const t = (el.innerText||'').trim() || (el.getAttribute('aria-label')||'');
                if (t) errs.push(t.slice(0,80));
            });
            return JSON.stringify(errs).slice(0, 800);
        }''')
    except Exception as e:
        return 'err_scan:' + str(e)[:100]

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
            await pg.fill('#Signup-EmailField', em)
            await pg.fill('#Signup-PasswordField', 'Abcd1234!xyz')
            await pg.click("button:has-text('Weiter')")
            await pg.wait_for_timeout(12000)
            txt = await pg.evaluate('document.body.innerText.slice(0,400)')
            if 'Schritt 2' not in txt and 'Vorname' not in txt:
                err = 'unknown'
                for k in ['ungültig','Tippfehler','bereits','Fehler','robot']:
                    if k in txt: err = k; break
                print('STEP1_FAIL', err, flush=True)
                report({'stage':'step1_fail','err':err,'email':em,'body':txt[:150],'n': n, **info})
                await b.close(); return
            print('STEP2_OK', flush=True)
            report({'stage':'step2_ok','email':em,'n': n, **info})
            st = await fill_step2(pg)
            print('FILL', st, flush=True)
            report({'stage':'filled','email':em,'res':st,'n': n, **info})
            clicked = False
            for btn in ["button:has-text('Konto erstellen')","button[type='submit']","button:has-text('Create account')"]:
                try:
                    el = await pg.query_selector(btn)
                    if el and await el.is_visible():
                        await el.click(); clicked = True; print('CREATE_CLICKED', flush=True); break
                except Exception: pass
            if not clicked:
                report({'stage':'create_btn_not_found','email':em,'n': n, **info})
            await pg.wait_for_timeout(12000)
            url = pg.url[:120]
            body = await pg.evaluate('document.body.innerText.slice(0,600)')
            errs = await get_form_errors(pg)
            print('URL', url, flush=True)
            print('ERRS', errs, flush=True)
            if '#/signup/2' in url or 'Schritt 2' in body or 'Vorname' in body:
                report({'stage':'step2_fail','email':em,'errs':errs,'body':body[:300],'n': n, **info})
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
            report({'stage':'no_cookie','email':em,'url':url,'body':body[:300],'n': n, **info})
            await b.close()
    except Exception as e:
        report({'stage':'exception','err':str(e)[:200],'n': n, **info})
        traceback.print_exc()

asyncio.run(main())
