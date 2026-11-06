(() => {
const sample = [
{id:"a17c92e1",path:"src/wallet.ts",tool:"write_file",old_hash:"3b2a9e1c",new_hash:"8d4f21aa",status:"pending",created_at:new Date().toISOString(),diff:"--- a/src/wallet.ts\n+++ b/src/wallet.ts\n@@ -1,3 +1,5 @@\n export function approve(tx: Transaction) {\n+  if (!tx || tx.amount <= 0) throw new Error('Invalid transaction');\n+  if (!wallet.isConnected()) throw new Error('Wallet not connected');\n   return wallet.send(tx);\n }"},
{id:"b42d8f06",path:"README.md",tool:"str_replace",old_hash:"0cc7ab31",new_hash:"9a2c4f80",status:"pending",created_at:new Date().toISOString(),diff:"--- a/README.md\n+++ b/README.md\n@@ -1,3 +1,3 @@\n-# Starter App\n+# PatchReview\n \n-A demo project.\n+Nothing writes to disk until the human accepts the diff."}
];
const proposals=(Array.isArray(window.PATCHREVIEW_DATA)?window.PATCHREVIEW_DATA:sample).map(p=>({...p}));
const list=document.getElementById("proposal-list");
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
function diffHtml(s){return String(s||"Diff unavailable").split("\n").map(line=>{const cls=line.startsWith("+")&&!line.startsWith("+++")?"add":line.startsWith("-")&&!line.startsWith("---")?"del":"ctx";return '<span class="'+cls+'">'+esc(line)+'</span>';}).join("");}
function stats(){["pending","accepted","rejected"].forEach(s=>document.getElementById(s+"-count").textContent=proposals.filter(p=>p.status===s).length);}
function render(){stats();if(!proposals.length){list.innerHTML='<div class="empty">No proposals yet. Your next file change will appear here.</div>';return;}
list.innerHTML=proposals.map(p=>{const done=p.status!=="pending";return '<article class="card '+(done?"done":"")+'" data-id="'+esc(p.id)+'"><div class="card-top"><h3 class="file-title">'+esc(p.path)+'</h3><span class="badge '+esc(p.status)+'">'+esc(p.status)+'</span></div><p class="meta">'+esc(p.id)+' · '+esc(p.old_hash||"—")+' → '+esc(p.new_hash||"—")+'<br>'+esc(p.tool||"write")+' · '+esc(new Date(p.created_at||Date.now()).toLocaleString())+'</p><div class="diff collapsed">'+diffHtml(p.diff_preview||p.diff)+'</div><div class="card-actions"><button class="action accept" data-action="accept" aria-label="Accept" '+(done?"disabled":"")+'>✓</button><button class="action reject" data-action="reject" aria-label="Reject" '+(done?"disabled":"")+'>×</button><button class="action" data-action="copy" aria-label="Copy diff">⧉</button><button class="text-action" data-action="expand">VIEW DIFF ↗</button></div></article>';}).join("");}
list.addEventListener("click",async e=>{const b=e.target.closest("button[data-action]");if(!b)return;const card=b.closest(".card"),p=proposals.find(x=>x.id===card.dataset.id);if(!p)return;const a=b.dataset.action;
if(a==="accept"||a==="reject"){if(p.status!=="pending")return;p.status=a==="accept"?"accepted":"rejected";render();}
else if(a==="copy"){try{await navigator.clipboard.writeText(p.diff_preview||p.diff||"");b.textContent="✓";}catch{b.textContent="!";}}
else if(a==="expand"){const d=card.querySelector(".diff");d.classList.toggle("collapsed");b.textContent=d.classList.contains("collapsed")?"VIEW DIFF ↗":"HIDE DIFF ↙";}
});
render();
})();
