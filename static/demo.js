'use strict';
// Each tour owns a separate server session; the user's session key is never changed.
(() => {
 let tour = null, timer = null;
 const panel = $('#demo-tour');
 const steps = [
  {title:'Meet Ishita: a customer receiving notifications', page:'simulator', next:'Show her first week',
   run:()=>api('customer/ishita/select','POST'),
   explain:()=>['ShopEasy tries to send useful shopping notifications without overwhelming a customer. We will follow Ishita from her first week to a personalized plan.', 'Her phone shows the notifications she can receive. Nothing has been opened yet. There is not enough history for a model estimate.', 'This is a separate practice simulation. Your own customers and preferences are saved.']},
  {title:'Week 1: Ishita responds to notifications', page:'insights', next:'Show the next four weeks',
   run:()=>api('customer/ishita/auto-play','POST'),
   explain:()=>['We played one week of scripted interactions for Ishita. The demo chose her responses; no real messages were sent.', `She now has ${state.selected_customer.history.length} completed week. Watch the recorded responses on the phone; Opened, Clicked and Ignored show what she actually did.`, 'A single week is not enough for a model estimate. The system keeps gathering evidence instead of guessing.']},
  {title:'Over time, Ishita pays less attention to promotions', page:'insights', next:'Explain the system’s decision',
   run:()=>api('sample-behaviour','POST'),
   explain:()=>['We fast-forwarded four more weeks. This sample also prepares the other example customers. Ishita starts responsive, then mostly ignores shopping promotions while still opening order updates.', `She now has ${state.selected_customer.history.length} completed weeks. The phone now shows her recorded week 5 responses. Compare these with week 1 using Back.`, 'These are scripted observations. They do not prove that she feels tired or has stopped shopping.']},
  {title:'Evidence → estimate → sending rules', page:'insights', next:'See what will be sent',
   explain:()=>{const a=state.selected_customer.analysis;return ['Read the observed trend, the separate ML estimate, and the sending-policy tier below. They answer different questions: what happened, what might happen, and what to send.', `Observed trend: ${a.trend}. Model estimate: ${pct(a.model_probability)} (${a.model_risk_tier}). Sending policy: ${a.risk_level}, with a promotional limit of ${a.frequency} per week.`, 'The estimate is uncertain and uncalibrated. The sending policy also considers behavior and preferences; it does not blindly copy the model.'];}},
  {title:'The planner turns the decision into a schedule', page:'planner', next:'Try a customer preference',
   explain:()=>{const c=state.selected_customer,x=c.comparison;return ['Her phone now shows only the notifications eligible for delivery. Each row explains why a message is allowed, delayed, or suppressed.', `For the same ${x.candidate_promotions} promotional candidates, the baseline allows ${x.baseline.allowed}; the adaptive plan allows ${x.adaptive.allowed}. These counts describe promotions only.`, 'Order updates are handled separately from promotions. Fewer planned promotions is a policy result, not proof of improved engagement.'];}},
  {title:'The customer has the final say', page:'planner', next:'Finish the walkthrough',
   run:()=>api('customer/ishita/preferences','PUT',{...state.selected_customer.preferences,promotional_opt_out:true}),
   explain:()=>['We switched on “Opt out of promotional notifications” for Ishita in this practice simulation.', 'Look at the phone: promotions have disappeared. In the table below, their suppression reasons now include her explicit preference. Order updates can still be delivered.', 'A customer preference overrides the recommendation. In normal use, change these choices in Simulate → Customer preference center.']},
  {title:'You are ready to try ShopEasy yourself', page:'overview', next:'Finish & return to my simulation',
   explain:()=>['You saw the full cycle: send notifications → record responses → estimate risk → adjust the plan → respect customer preferences.', 'Try Simulate with Guest: choose Open, Ignore, Dismiss, or Mute for each delivered notification, then save the week. Visit Customer Insights and Notification Planner to see the effect.', 'Use Model Evaluation to inspect the model’s measured strengths and limitations. Finish below to return to your own saved simulation.']}
 ];
 function stopTimer(){clearInterval(timer);timer=null;}
 function lock(value){$('#content').classList.toggle('tour-results',value);if(value)$('#content').querySelectorAll('button,input,select').forEach(control=>control.disabled=true);document.querySelector('nav').inert=value;document.querySelectorAll('[data-page]').forEach(b=>b.disabled=value);if(value)$('#content').querySelectorAll('aside').forEach(node=>node.inert=true);$('#reset').disabled=value;$('#report').disabled=value;$('#demo').disabled=value;}
 function paint(error=''){
  const s=steps[tour.index], lines=tour.loading?['Preparing the next part of Ishita’s story. Please wait…','The results below will update when this step is ready.','Your own simulation remains saved.']:s.explain();
  panel.innerHTML=`<div class="tour-top"><span class="badge">Practice simulation · Step ${tour.index+1} of ${steps.length}</span><button id="tour-exit" ${tour.loading?'disabled':''}>Exit demo</button></div><progress max="${steps.length}" value="${tour.index+1}" aria-label="Walkthrough progress"></progress><h2 id="tour-title" tabindex="-1">${e(s.title)}</h2><div class="tour-stage">${tour.loading?'':demoPhone(state.selected_customer,tour.index)}<div class="tour-story" aria-live="polite">${lines.map((line,i)=>`<p><strong>${['What happened','What to notice','Why it matters'][i]}</strong>${e(line)}</p>`).join('')}</div></div>${error?`<p class="error" role="alert">${e(error)} Use Next to retry this step, or exit safely.</p>`:''}<div class="tour-controls"><button id="tour-back" ${tour.loading||tour.index===0?'disabled':''}>← Back</button><button id="tour-next" class="primary" ${tour.loading?'disabled':''}>${tour.loading?'Preparing this step…':e(error?'Retry step':s.next+' →')}</button><button id="tour-auto" ${tour.loading?'disabled':''}>${tour.auto?'Pause automatic playback':'Play automatically'}</button><span id="tour-count" class="muted">${tour.auto?'Next step in 25 seconds':'Paused · Read at your own pace'}</span></div><p class="tour-note">The page below shows this step’s real simulation results. Editing is paused during the tour; Exit demo restores your workspace.</p>`;
  $('#tour-exit').onclick=finish;
  $('#tour-back').onclick=()=>{tour.auto=false;show(tour.index-1);};
  $('#tour-next').onclick=()=>error?show(tour.index):tour.index===steps.length-1?finish():show(tour.index+1);
  $('#tour-auto').onclick=()=>{tour.auto=!tour.auto;paint();schedule();};
 }
 function schedule(){
  stopTimer();if(!tour||!tour.auto||tour.loading)return;
  let seconds=25;
  timer=setInterval(()=>{
   if(document.hidden)return; // Do not skip explanations while the tab is hidden.
   seconds--;$('#tour-count').textContent=`${tour.index===steps.length-1?'Return to your simulation':'Next step'} in ${seconds} seconds`;
   if(seconds<=0){stopTimer();tour.index===steps.length-1?finish():show(tour.index+1);}
  },1000);
 }
 async function show(index){
  stopTimer();tour.index=index;tour.loading=true;paint();
  try{
   if(tour.snapshots[index]) state=structuredClone(tour.snapshots[index]);
   else {
    // Restore the latest actual server state before applying the next step.
    state=await api('state');
    if(steps[index].run)await steps[index].run();
    state=await api('state');tour.snapshots[index]=structuredClone(state);
   }
   page=steps[index].page;render();lock(true);tour.loading=false;paint();
   panel.scrollIntoView({behavior:'smooth',block:'start'});$('#tour-title').focus({preventScroll:true});schedule();
  }catch(err){tour.loading=false;tour.auto=false;paint(err.message);}
 }
 async function finish(){
  if(!tour||tour.loading)return;
  stopTimer();simulation=tour.original;page=tour.originalPage;tour=null;
  panel.hidden=true;panel.innerHTML='';lock(false);
  try{await reload();notice('Demo finished. Your own simulation has been restored.');$('#demo').focus();}
  catch(err){notice(`Your simulation is selected again. Refresh to reload it. ${err.message}`,true);}
 }
 $('#demo').onclick=async()=>{
  if(busy||tour||!state)return;
  tour={original:simulation,originalPage:page,index:0,snapshots:[],loading:true,auto:false};
  simulation=crypto.randomUUID();panel.hidden=false;lock(true);
  await show(0);
 };
})();
