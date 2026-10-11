const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
test('one click downloads PDF only for the selected customer and simulation',async()=>{
 const button={disabled:false,textContent:''};let requested,downloaded,notice;
 const context=vm.createContext({$:()=>button,state:{selected_customer:{id:'ishita',name:'Ishita'}},busy:false,simulation:'session-id',encodeURIComponent,setTimeout(){},URL:{createObjectURL(){return 'blob:pdf';},revokeObjectURL(){}},notice:m=>notice=m,fetch:async(path,options)=>{requested={path,options};return {ok:true,headers:{get:key=>key==='Content-Type'?'application/pdf':'attachment; filename="shopeasy-ishita-week-6-report.pdf"'},blob:async()=>new Blob(['%PDF-test'],{type:'application/pdf'})};},Blob,document:{body:{appendChild(){}},createElement(){return {click(){downloaded=this.download;},remove(){}};}}});
 vm.runInContext(fs.readFileSync('static/report.js','utf8'),context);
 await button.onclick();
 assert.equal(requested.path,'/api/customer/ishita/report.pdf');
 assert.equal(requested.options.headers['X-Simulation-ID'],'session-id');
 assert.equal(downloaded,'shopeasy-ishita-week-6-report.pdf');
 assert.match(notice,/PDF report has been downloaded/);
 assert.equal(button.disabled,false);
});
