(()=>{
const KEY='pgpt-ui-v8',LEGACY=['pgpt-ui-v7','pgpt-ui-v6','pgpt-ui-v5'],ENDPOINT='/api/chats';
let hydrating=true,lastSent='';
function localState(){for(const key of [KEY,...LEGACY]){try{const raw=localStorage.getItem(key);if(!raw)continue;const value=JSON.parse(raw);if(value?.chats?.length)return{raw:JSON.stringify(value),value}}catch{}}return null}
function newest(value){return Math.max(0,...(value?.chats||[]).map(c=>Date.parse(c.updatedAt||c.created||0)||0))}
async function persist(raw,keepalive=false){if(!raw||raw===lastSent)return;lastSent=raw;try{const response=await fetch(ENDPOINT,{method:'POST',headers:{'Content-Type':'application/json'},body:raw,keepalive});if(!response.ok)lastSent=''}catch{lastSent=''}}
async function hydrate(){try{const response=await fetch(ENDPOINT,{cache:'no-store'});if(!response.ok)throw new Error('chat state unavailable');const payload=await response.json(),remote=payload.state,local=localState();if(remote?.chats?.length){const remoteRaw=JSON.stringify(remote);if(!local||newest(remote)>=newest(local.value)){if(!local||local.raw!==remoteRaw){localStorage.setItem(KEY,remoteRaw);location.reload();return}lastSent=remoteRaw}else await persist(local.raw)}else if(local?.value?.chats?.length)await persist(local.raw)}catch{}finally{hydrating=false}}
setInterval(()=>{if(hydrating)return;const local=localState();if(local)persist(local.raw)},500);
window.addEventListener('pagehide',()=>{const local=localState();if(!local||local.raw===lastSent)return;try{navigator.sendBeacon(ENDPOINT,new Blob([local.raw],{type:'application/json'}))}catch{}});
const footer=document.querySelector('.footer');if(footer)footer.innerHTML='Chats are saved locally on disk.<br>Personal skills: ~/.config/pgpt/skills/';
hydrate();
})();
