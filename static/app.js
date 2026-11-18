(function(){
const R=document.documentElement,$=(s,r=document)=>r.querySelector(s),$$=(s,r=document)=>[...r.querySelectorAll(s)];
const mob=()=>matchMedia('(max-width:900px)').matches;
const sb=$('#sbtn');if(sb)sb.onclick=()=>{if(mob())R.classList.toggle('open');else{R.classList.toggle('collapsed');try{localStorage.setItem('gg-side',R.classList.contains('collapsed')?'1':'0')}catch(e){}}};
const bk=$('.bk');if(bk)bk.onclick=()=>R.classList.remove('open');
const tb=$('#tbtn');if(tb)tb.onclick=()=>{const d=R.dataset.theme==='dark'?'light':'dark';R.dataset.theme=d;try{localStorage.setItem('gg-theme',d)}catch(e){}};
document.addEventListener('click',e=>{$$('details.menu[open]').forEach(m=>{if(!m.contains(e.target))m.open=false});
 const o=e.target.closest('[data-open]');if(o){const d=document.getElementById(o.dataset.open);d&&d.showModal();}
 const c=e.target.closest('[data-close]');if(c)c.closest('dialog').close();
 if(e.target.tagName==='DIALOG')e.target.close();
 const t=e.target.closest('.tabs button');if(t)tab(t.dataset.t);
 const x=e.target.closest('.toast button');if(x)x.parentNode.remove()});
function tab(id){const b=$(`.tabs button[data-t="${id}"]`);if(!b)return false;$$('.tabs button,.pn').forEach(n=>n.classList.remove('on'));b.classList.add('on');const p=document.getElementById(id);p&&p.classList.add('on');return true}
// confirmation dialogs for sensitive forms
const cd=$('#cd');let pend=null;
document.addEventListener('submit',e=>{const f=e.target;if(!f.dataset.confirm||f.dataset.ok)return;e.preventDefault();pend=f;$('#cdt').textContent=f.dataset.title||'Please confirm';$('#cdm').textContent=f.dataset.confirm;cd.showModal()});
const cy=$('#cdy');if(cy)cy.onclick=()=>{if(pend){pend.dataset.ok='1';cd.close();pend.submit()}};
setTimeout(()=>$$('.toast.ok').forEach(t=>t.remove()),6000);
const h=location.hash.slice(1);if(h==='freeze'){const d=document.getElementById('fm');d&&d.showModal()}else if(h)tab(h);
})();
