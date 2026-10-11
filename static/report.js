 'use strict';
(() => {
 let downloading=false;
 $('#report').onclick=async()=>{
  if(!state||busy||downloading)return;
  const c=state.selected_customer, button=$('#report');
  downloading=true;button.disabled=true;button.textContent='Generating PDF…';
  try {
   const response=await fetch(`/api/customer/${encodeURIComponent(c.id)}/report.pdf`,{headers:{'X-Simulation-ID':simulation}});
   if(!response.ok){const result=await response.json();throw new Error(result.detail||'Could not generate the PDF. Please retry.');}
   if(!response.headers.get('Content-Type')?.includes('application/pdf'))throw new Error('The server did not return a PDF. Please retry.');
   const blob=await response.blob(),url=URL.createObjectURL(blob),link=document.createElement('a');
   link.href=url;link.download=response.headers.get('Content-Disposition')?.match(/filename="([^"]+)"/)?.[1]||`shopeasy-${c.id}-report.pdf`;
   document.body.appendChild(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),30000);
   notice(`${c.name}’s PDF report has been downloaded.`);
  }catch(error){notice(error.message,true);}
  finally{downloading=false;button.disabled=false;button.textContent='↓ Download PDF report';}
 };
})();
