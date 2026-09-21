const fs=require('fs'),path=require('path'),assert=require('assert');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'../..');process.chdir(root);
const config=Object.fromEntries(fs.readFileSync('.env','utf8').split('\n').filter(x=>x.includes('=')&&!x.startsWith('#')).map(x=>{const i=x.indexOf('=');return [x.slice(0,i),x.slice(i+1)];}));
const password=fs.readFileSync(path.join(path.dirname(config.AI_SOC_IDENTITY_DIR),'admin-credentials.txt'),'utf8').split('Password: ')[1].trim();
const imageDir=path.join(root,'docs/development/screenshots');fs.mkdirSync(imageDir,{recursive:true});
(async()=>{
const browser=await chromium.launch({headless:true,executablePath:process.env.AI_SOC_BROWSER_EXECUTABLE||undefined});
const context=await browser.newContext({viewport:{width:1440,height:1000},acceptDownloads:true});const page=await context.newPage();
const errors=[];page.on('pageerror',e=>errors.push(e.message));
let createdUser;
const checks=[]; const pass=x=>{checks.push(x);console.log('PASS',x);};
try {
 const fixture='browser-fixture-'+Date.now();
 const machine={Authorization:'Bearer '+config.AI_SOC_API_KEY};
 const stored=await context.request.post('http://127.0.0.1:8400/alerts',{headers:machine,data:{alert_id:fixture,rule_description:fixture,raw_alert:{source:'controlled browser acceptance fixture',message:'Synthetic SSH test; no measured flow'}}});assert(stored.ok());
 const label=await context.request.post('http://127.0.0.1:8400/feedback/'+fixture,{headers:machine,data:{analyst_id:'browser-fixture-author',true_label:'ATTACK',notes:'Synthetic UI acceptance; ineligible for training without complete flow measurements'}});assert(label.ok());
 await page.goto('http://127.0.0.1:5050/login');
 await page.getByLabel('Username',{exact:true}).fill('admin');await page.getByLabel('Password',{exact:true}).fill(password);
 await page.getByRole('button',{name:'Sign in',exact:true}).click();await page.waitForURL('http://127.0.0.1:5050/');
 await page.waitForFunction(()=>document.getElementById('mb-svc-count').textContent==='8/8',null,{timeout:30000});
 await page.screenshot({path:path.join(imageDir,'command-center.png'),fullPage:false,animations:'disabled'});
 pass('Administrator signs in through the browser and command center executes without script errors');
 await page.goto('http://127.0.0.1:5050/reviews');
 await page.locator('#rules article').first().waitFor();await page.waitForFunction(()=>!document.querySelector('#feedback').textContent.includes('Loading'));
 await page.screenshot({path:path.join(imageDir,'reviews.png'),fullPage:false,animations:'disabled'});
 const pending=page.locator('#feedback article').filter({hasText:fixture});
 await pending.waitFor();
   await pending.locator('summary').click();await pending.locator('details pre').waitFor();
   await pending.locator('textarea').fill('Browser acceptance of a controlled smoke label; source inspected.');
   const response=page.waitForResponse(r=>r.url().includes('/api/feedback/reviews/')&&r.request().method()==='POST');
   await pending.getByRole('button',{name:'Approve label',exact:true}).click();assert((await response).ok());
   await page.getByRole('status').filter({hasText:'Saved.'}).waitFor();pass('Reviewer inspects source evidence and submits an independent label decision');
 if(!await page.getByRole('link',{name:'Download approved YAML'}).count()){
   const draft=page.locator('#rules article').filter({has:page.getByRole('button',{name:'Approve for export',exact:true})}).first();
   await draft.waitFor();
   await draft.getByPlaceholder('Review notes',{exact:true}).fill('Controlled browser export acceptance; reviewed displayed draft.');
   await draft.getByRole('button',{name:'Approve for export',exact:true}).click();
   await page.getByRole('link',{name:'Download approved YAML'}).first().waitFor();
 }
 const downloadPromise=page.waitForEvent('download');await page.getByRole('link',{name:'Download approved YAML'}).first().click();
 const download=await downloadPromise;const output=path.join(root,'../../work/browser-rule.yaml');await download.saveAs(output);assert(fs.readFileSync(output,'utf8').includes('detection:'));pass('Approved rule downloads as a YAML file from the browser');
 await page.getByRole('link',{name:'Account & access',exact:true}).click();await page.locator('#users tr').first().waitFor();
 await page.screenshot({path:path.join(imageDir,'accounts.png'),fullPage:false,animations:'disabled'});
 const username='browser-check-'+Date.now();const testPassword=require('crypto').randomBytes(24).toString('base64url');
 await page.getByLabel('Username',{exact:true}).fill(username);await page.getByLabel('Initial password',{exact:true}).fill(testPassword);await page.getByLabel('Role',{exact:true}).selectOption('viewer');
 await page.getByRole('button',{name:'Create account',exact:true}).click();
 const row=page.locator('#users tr').filter({hasText:username});await row.waitFor();createdUser=username;await row.getByRole('button',{name:'Disable',exact:true}).click();await row.getByRole('button',{name:'Enable',exact:true}).waitFor();pass('Account administration creates and disables a test viewer through the UI');
 await page.getByRole('button',{name:'Sign out',exact:true}).click();await page.waitForURL('**/login');
 await page.goto('http://127.0.0.1:5050/reviews');await page.waitForURL('**/login');pass('Sign-out prevents subsequent access to authenticated pages');
 assert.deepEqual(errors,[]);
 const report={status:'passed',verified_at:new Date().toISOString(),browser:'Isolated headless Chromium with a fresh profile',checks,page_errors:errors,screenshots:['command-center.png','reviews.png','accounts.png'],desktop_unlock_required:false};
 fs.writeFileSync('docs/development/browser-verification.json',JSON.stringify(report,null,2)+'\n');
}finally{
 if(createdUser){
  const me=await context.request.get('http://127.0.0.1:5050/api/auth/me');
  if(me.ok()){
   const info=await me.json();
   const disabled=await context.request.patch('http://127.0.0.1:5050/api/auth/users/'+createdUser,{headers:{'X-CSRF-Token':info.csrf},data:{active:false}});
   assert(disabled.ok(),'Failed to disable browser acceptance account');
  }
 }
 await browser.close();
}
})().catch(e=>{console.error(e.stack);process.exit(1)});
