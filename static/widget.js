(function(){
'use strict';
var SCRIPT=document.currentScript;
var API_KEY=SCRIPT?SCRIPT.getAttribute('data-key'):'';
var BASE_URL='';
if(SCRIPT&&SCRIPT.src){var u=new URL(SCRIPT.src);BASE_URL=u.origin;}
var isDemo=!API_KEY||API_KEY==='DEMO_KEY';
var state={step:1,userFile:null,userPreview:'',productImg:'',productId:'',productUrl:'',products:[],resultImg:'',score:0,scoreLabel:'',colorNote:'',fitNote:'',styleNote:'',recommendations:[],loading:false};

function injectStyles(){
var css=`
.fitsnap-widget *,.fitsnap-widget *::before,.fitsnap-widget *::after{box-sizing:border-box;margin:0;padding:0;}
.fitsnap-widget{--fs-primary:#3D1F0D;--fs-accent:#C17F4A;--fs-success:#2D6A4F;--fs-warning:#E76F51;--fs-bg:#FFFFFF;--fs-surface:#F8F4F0;--fs-text:#1a1a1a;--fs-text-secondary:#666;font-family:system-ui,-apple-system,sans-serif;line-height:1.5;color:var(--fs-text);}
.fitsnap-trigger{position:fixed;bottom:24px;right:24px;z-index:999998;background:var(--fs-primary);color:#fff;border:none;padding:14px 28px;border-radius:50px;font-size:16px;font-weight:600;cursor:pointer;box-shadow:0 4px 20px rgba(61,31,13,.35);transition:all .3s ease;display:flex;align-items:center;gap:8px;}
.fitsnap-trigger:hover{transform:translateY(-2px);box-shadow:0 6px 28px rgba(61,31,13,.45);background:#4a2710;}
.fitsnap-overlay{position:fixed;inset:0;z-index:999999!important;background:rgba(0,0,0,.6);backdrop-filter:blur(4px);display:flex;align-items:center;justify-content:center;opacity:0;visibility:hidden;transition:all .3s ease;}
.fitsnap-overlay.fs-open{opacity:1;visibility:visible;}
.fitsnap-modal{background:var(--fs-bg);border-radius:20px;width:min(680px,94vw);max-height:90vh;overflow-y:auto;position:relative;box-shadow:0 20px 60px rgba(0,0,0,.3);animation:fsSlideUp .4s ease;}
@keyframes fsSlideUp{from{transform:translateY(30px);opacity:0}to{transform:translateY(0);opacity:1}}
.fitsnap-close{position:absolute;top:12px;right:12px;width:36px;height:36px;border-radius:50%;border:none;background:var(--fs-surface);cursor:pointer;font-size:20px;display:flex;align-items:center;justify-content:center;z-index:10;transition:background .2s;}
.fitsnap-close:hover{background:#e8e0d8;}
.fitsnap-header{padding:24px 24px 0;text-align:center;}
.fitsnap-steps{display:flex;justify-content:center;gap:8px;margin-bottom:20px;}
.fitsnap-step-dot{width:10px;height:10px;border-radius:50%;background:#ddd;transition:all .3s;}
.fitsnap-step-dot.active{background:var(--fs-accent);transform:scale(1.3);}
.fitsnap-step-dot.done{background:var(--fs-success);}
.fitsnap-body{padding:24px;}
.fitsnap-upload-zone{border:2px dashed var(--fs-accent);border-radius:16px;padding:40px 20px;text-align:center;cursor:pointer;transition:all .3s;background:var(--fs-surface);}
.fitsnap-upload-zone:hover{border-color:var(--fs-primary);background:#f3ede7;}
.fitsnap-upload-zone.has-image{border-style:solid;border-color:var(--fs-success);}
.fitsnap-upload-icon{font-size:48px;margin-bottom:12px;}
.fitsnap-upload-title{font-size:18px;font-weight:600;color:var(--fs-primary);margin-bottom:4px;}
.fitsnap-upload-sub{font-size:13px;color:var(--fs-text-secondary);}
.fitsnap-preview-img{max-height:200px;border-radius:12px;margin-top:16px;object-fit:contain;}
.fitsnap-btns{display:flex;gap:10px;margin-top:20px;flex-wrap:wrap;}
.fitsnap-btn{padding:12px 24px;border-radius:12px;border:none;font-size:15px;font-weight:600;cursor:pointer;transition:all .2s;min-height:44px;flex:1;text-align:center;}
.fitsnap-btn-primary{background:var(--fs-primary);color:#fff;}
.fitsnap-btn-primary:hover{background:#4a2710;}
.fitsnap-btn-secondary{background:var(--fs-surface);color:var(--fs-primary);border:1.5px solid var(--fs-accent);}
.fitsnap-btn-secondary:hover{background:#efe8e0;}
.fitsnap-btn:disabled{opacity:.5;cursor:not-allowed;}
.fitsnap-product-preview{margin-top:20px;padding:16px;background:var(--fs-surface);border-radius:12px;display:flex;align-items:center;gap:12px;}
.fitsnap-product-preview img{width:60px;height:80px;object-fit:cover;border-radius:8px;}
.fitsnap-product-preview .pp-label{font-size:12px;color:var(--fs-text-secondary);}
.fitsnap-product-preview .pp-name{font-size:14px;font-weight:600;}
.fitsnap-loading{text-align:center;padding:40px 20px;}
.fitsnap-spinner{width:56px;height:56px;border:4px solid var(--fs-surface);border-top-color:var(--fs-accent);border-radius:50%;animation:fsSpin 1s linear infinite;margin:0 auto 20px;}
@keyframes fsSpin{to{transform:rotate(360deg)}}
.fitsnap-loading-msg{font-size:16px;font-weight:500;color:var(--fs-primary);min-height:24px;}
.fitsnap-loading-sub{font-size:13px;color:var(--fs-text-secondary);margin-top:8px;}
.fitsnap-result{display:flex;gap:24px;flex-wrap:wrap;}
.fitsnap-result-img{flex:1;min-width:200px;}
.fitsnap-result-img img{width:100%;border-radius:16px;box-shadow:0 4px 16px rgba(0,0,0,.1);}
.fitsnap-result-info{flex:1;min-width:240px;}
.fitsnap-score-ring{width:120px;height:120px;margin:0 auto 16px;position:relative;}
.fitsnap-score-ring svg{transform:rotate(-90deg);}
.fitsnap-score-ring circle{fill:none;stroke-width:8;}
.fitsnap-score-ring .ring-bg{stroke:#e8e0d8;}
.fitsnap-score-ring .ring-fg{stroke:var(--fs-success);stroke-linecap:round;transition:stroke-dashoffset 1.5s ease;}
.fitsnap-score-num{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:36px;font-weight:700;color:var(--fs-primary);}
.fitsnap-score-label{text-align:center;font-size:16px;font-weight:600;margin-bottom:16px;}
.fitsnap-notes{display:flex;flex-direction:column;gap:8px;margin-bottom:16px;}
.fitsnap-note{display:flex;align-items:flex-start;gap:8px;font-size:13px;padding:8px 12px;background:var(--fs-surface);border-radius:10px;}
.fitsnap-note-icon{font-size:16px;flex-shrink:0;}
.fitsnap-banner{padding:12px 16px;border-radius:12px;text-align:center;font-weight:600;font-size:14px;margin-bottom:16px;}
.fitsnap-banner.success{background:#e8f5e9;color:var(--fs-success);}
.fitsnap-banner.warning{background:#fff3e0;color:#e65100;}
.fitsnap-recs{margin-top:16px;}
.fitsnap-recs h3{font-size:16px;margin-bottom:12px;color:var(--fs-primary);}
.fitsnap-rec-card{display:flex;gap:12px;padding:12px;background:var(--fs-surface);border-radius:12px;margin-bottom:10px;align-items:center;}
.fitsnap-rec-card img{width:64px;height:80px;object-fit:cover;border-radius:8px;flex-shrink:0;}
.fitsnap-rec-info{flex:1;min-width:0;}
.fitsnap-rec-info .rn{font-weight:600;font-size:14px;}
.fitsnap-rec-info .rp{font-size:13px;color:var(--fs-accent);font-weight:600;}
.fitsnap-rec-info .rr{font-size:12px;color:var(--fs-text-secondary);margin-top:2px;}
.fitsnap-rec-btn{padding:8px 14px;border-radius:8px;border:none;background:var(--fs-primary);color:#fff;font-size:12px;font-weight:600;cursor:pointer;white-space:nowrap;min-height:44px;}
.fitsnap-rec-btn:hover{background:#4a2710;}
.fitsnap-error{text-align:center;padding:20px;color:var(--fs-warning);font-weight:500;}
@media(max-width:768px){
.fitsnap-modal{width:100vw;height:100vh;max-height:100vh;border-radius:0;}
.fitsnap-result{flex-direction:column;}
.fitsnap-trigger{bottom:16px;right:16px;padding:12px 20px;font-size:14px;}
}
`;
var s=document.createElement('style');s.textContent=css;document.head.appendChild(s);
}

function detectProductImage(){
var og=document.querySelector('meta[property="og:image"]');
if(og&&og.content)return og.content;
var imgs=document.querySelectorAll('main img, .product img, #product img, article img, [class*=product] img');
var best='',bestArea=0;
imgs.forEach(function(im){
var a=(im.naturalWidth||im.width||0)*(im.naturalHeight||im.height||0);
if(a>bestArea){bestArea=a;best=im.src;}
});
if(best)return best;
var all=document.querySelectorAll('img');
all.forEach(function(im){
var a=(im.naturalWidth||im.width||0)*(im.naturalHeight||im.height||0);
if(a>bestArea){bestArea=a;best=im.src;}
});
return best;
}

function renderStepDots(container){
container.innerHTML='';
for(var i=1;i<=3;i++){
var d=document.createElement('div');d.className='fitsnap-step-dot';
if(i<state.step)d.classList.add('done');
if(i===state.step)d.classList.add('active');
container.appendChild(d);
}
}

function renderUpload(body){
body.innerHTML='';
var zone=document.createElement('div');
zone.className='fitsnap-upload-zone'+(state.userPreview?' has-image':'');
if(state.userPreview){
zone.innerHTML='<img class="fitsnap-preview-img" src="'+state.userPreview+'" alt="Your photo"><p style="margin-top:8px;font-size:13px;color:var(--fs-success);font-weight:600;">✓ Photo uploaded — tap to change</p>';
}else{
zone.innerHTML='<div class="fitsnap-upload-icon">📸</div><div class="fitsnap-upload-title">Upload your photo for virtual try-on</div><div class="fitsnap-upload-sub">Full body photo works best</div>';
}
var inp=document.createElement('input');inp.type='file';inp.accept='image/*';inp.style.display='none';
inp.onchange=function(e){
var f=e.target.files[0];if(!f)return;
if(f.size>10*1024*1024){alert('Please use a smaller photo (under 10MB)');return;}
state.userFile=f;
var r=new FileReader();r.onload=function(ev){state.userPreview=ev.target.result;renderModal();};r.readAsDataURL(f);
};
zone.onclick=function(){inp.click();};
body.appendChild(zone);body.appendChild(inp);

if(state.productImg){
var pp=document.createElement('div');pp.className='fitsnap-product-preview';
pp.innerHTML='<img src="'+state.productImg+'" alt="Product"><div><div class="pp-label">Trying on:</div><div class="pp-name">Selected outfit</div></div>';
body.appendChild(pp);
}

var btns=document.createElement('div');btns.className='fitsnap-btns';
var tryBtn=document.createElement('button');
tryBtn.className='fitsnap-btn fitsnap-btn-primary';
tryBtn.textContent='Try This Outfit →';
tryBtn.disabled=!state.userFile;
tryBtn.onclick=function(){startTryOn();};
btns.appendChild(tryBtn);
body.appendChild(btns);

if(!state.productImg&&state.products.length>0){
var grid=document.createElement('div');
grid.style.cssText='margin-top:20px;';
grid.innerHTML='<p style="font-size:14px;font-weight:600;margin-bottom:12px;">Select a product to try on:</p>';
var gw=document.createElement('div');gw.style.cssText='display:grid;grid-template-columns:repeat(auto-fill,minmax(100px,1fr));gap:8px;';
state.products.slice(0,8).forEach(function(p){
var card=document.createElement('div');
card.style.cssText='cursor:pointer;border-radius:10px;overflow:hidden;border:2px solid transparent;transition:border .2s;';
card.innerHTML='<img src="'+p.image_url+'" style="width:100%;height:120px;object-fit:cover;" alt="'+p.name+'"><p style="font-size:11px;padding:4px;text-align:center;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">'+p.name+'</p>';
card.onclick=function(){state.productImg=p.image_url;state.productId=p.id;state.productUrl=p.product_url;renderModal();};
card.onmouseenter=function(){card.style.borderColor='var(--fs-accent)';};
card.onmouseleave=function(){card.style.borderColor='transparent';};
gw.appendChild(card);
});
grid.appendChild(gw);body.appendChild(grid);
}
}

var loadingMessages=['Preparing your photo...','Detecting outfit type...','Fitting the outfit on you...','Rating your look...'];
var msgIndex=0;

function renderProcessing(body){
body.innerHTML='';
var ld=document.createElement('div');ld.className='fitsnap-loading';
ld.innerHTML='<div class="fitsnap-spinner"></div><div class="fitsnap-loading-msg" id="fs-load-msg">'+loadingMessages[0]+'</div><div class="fitsnap-loading-sub">Usually takes 30-40 seconds</div>';
body.appendChild(ld);
msgIndex=0;
var iv=setInterval(function(){
msgIndex++;if(msgIndex>=loadingMessages.length)msgIndex=loadingMessages.length-1;
var el=document.getElementById('fs-load-msg');
if(el)el.textContent=loadingMessages[msgIndex];
if(state.step!==2)clearInterval(iv);
},6000);
}

function renderResult(body){
body.innerHTML='';
var wrap=document.createElement('div');wrap.className='fitsnap-result';

var imgCol=document.createElement('div');imgCol.className='fitsnap-result-img';
imgCol.innerHTML='<img src="'+state.resultImg+'" alt="Try-on result">';
wrap.appendChild(imgCol);

var infoCol=document.createElement('div');infoCol.className='fitsnap-result-info';

var circ=377;var pct=state.score/100;var offset=circ-(pct*circ);
var ringColor=state.score>=85?'var(--fs-success)':state.score>=70?'var(--fs-accent)':'var(--fs-warning)';
infoCol.innerHTML='<div class="fitsnap-score-ring"><svg width="120" height="120" viewBox="0 0 120 120"><circle class="ring-bg" cx="60" cy="60" r="54"/><circle class="ring-fg" cx="60" cy="60" r="54" style="stroke:'+ringColor+';stroke-dasharray:'+circ+';stroke-dashoffset:'+offset+'"/></svg><div class="fitsnap-score-num">'+state.score+'</div></div><div class="fitsnap-score-label" style="color:'+ringColor+'">'+state.scoreLabel+'</div>';

var notes=document.createElement('div');notes.className='fitsnap-notes';
notes.innerHTML='<div class="fitsnap-note"><span class="fitsnap-note-icon">🎨</span><span>'+state.colorNote+'</span></div><div class="fitsnap-note"><span class="fitsnap-note-icon">📐</span><span>'+state.fitNote+'</span></div><div class="fitsnap-note"><span class="fitsnap-note-icon">✨</span><span>'+state.styleNote+'</span></div>';
infoCol.appendChild(notes);

if(state.score>=85){
var ban=document.createElement('div');ban.className='fitsnap-banner success';ban.textContent='✓ This outfit suits you perfectly!';
infoCol.appendChild(ban);
var btns=document.createElement('div');btns.className='fitsnap-btns';
if(state.productUrl){
var shop=document.createElement('button');shop.className='fitsnap-btn fitsnap-btn-primary';shop.textContent='Shop Now';shop.onclick=function(){window.open(state.productUrl,'_blank');};btns.appendChild(shop);
}
var retry=document.createElement('button');retry.className='fitsnap-btn fitsnap-btn-secondary';retry.textContent='Try Another';retry.onclick=function(){resetState();renderModal();};btns.appendChild(retry);
infoCol.appendChild(btns);
}else{
var ban=document.createElement('div');ban.className='fitsnap-banner warning';ban.textContent='We found better matches for you';
infoCol.appendChild(ban);

if(state.recommendations.length>0){
var recs=document.createElement('div');recs.className='fitsnap-recs';
recs.innerHTML='<h3>Better Options From Our Collection</h3>';
state.recommendations.forEach(function(r){
var card=document.createElement('div');card.className='fitsnap-rec-card';
card.innerHTML='<img src="'+r.image_url+'" alt="'+r.name+'"><div class="fitsnap-rec-info"><div class="rn">'+r.name+'</div><div class="rp">'+r.price+'</div><div class="rr">'+r.reason+'</div></div>';
var btn=document.createElement('button');btn.className='fitsnap-rec-btn';btn.textContent='Try This On';
btn.onclick=function(){state.productImg=r.image_url;state.productId=r.id;state.productUrl=r.product_url;state.step=1;state.resultImg='';renderModal();};
card.appendChild(btn);recs.appendChild(card);
});
infoCol.appendChild(recs);
}
var btns=document.createElement('div');btns.className='fitsnap-btns';btns.style.marginTop='12px';
if(state.productUrl){
var anyway=document.createElement('button');anyway.className='fitsnap-btn fitsnap-btn-secondary';anyway.textContent='Try It Anyway';anyway.onclick=function(){window.open(state.productUrl,'_blank');};btns.appendChild(anyway);
}
var retry=document.createElement('button');retry.className='fitsnap-btn fitsnap-btn-secondary';retry.textContent='Try Another';retry.onclick=function(){resetState();renderModal();};btns.appendChild(retry);
infoCol.appendChild(btns);
}
wrap.appendChild(infoCol);body.appendChild(wrap);
}

function renderModal(){
var overlay=document.getElementById('fitsnap-overlay');if(!overlay)return;
var dots=overlay.querySelector('.fitsnap-steps');if(dots)renderStepDots(dots);
var body=overlay.querySelector('.fitsnap-body');if(!body)return;
if(state.step===1)renderUpload(body);
else if(state.step===2)renderProcessing(body);
else if(state.step===3)renderResult(body);
}

function resetState(){
state.step=1;state.userFile=null;state.userPreview='';state.resultImg='';state.score=0;
state.scoreLabel='';state.colorNote='';state.fitNote='';state.styleNote='';state.recommendations=[];
state.productImg=detectProductImage();
}

function openModal(){
var overlay=document.getElementById('fitsnap-overlay');
if(!overlay){buildModal();overlay=document.getElementById('fitsnap-overlay');}
state.step=1;if(!state.productImg)state.productImg=detectProductImage();
renderModal();
setTimeout(function(){overlay.classList.add('fs-open');},10);
}

function closeModal(){
var overlay=document.getElementById('fitsnap-overlay');
if(overlay)overlay.classList.remove('fs-open');
}

function buildModal(){
var overlay=document.createElement('div');overlay.id='fitsnap-overlay';overlay.className='fitsnap-widget fitsnap-overlay';
overlay.onclick=function(e){if(e.target===overlay)closeModal();};
var modal=document.createElement('div');modal.className='fitsnap-modal';
var closeBtn=document.createElement('button');closeBtn.className='fitsnap-close';closeBtn.innerHTML='✕';closeBtn.onclick=closeModal;
var header=document.createElement('div');header.className='fitsnap-header';
header.innerHTML='<div class="fitsnap-steps"></div>';
var body=document.createElement('div');body.className='fitsnap-body';
modal.appendChild(closeBtn);modal.appendChild(header);modal.appendChild(body);
overlay.appendChild(modal);document.body.appendChild(overlay);
}

function startTryOn(){
if(!state.userFile){alert('Please upload a photo first');return;}
if(!state.productImg){alert('No product image found');return;}
state.step=2;renderModal();

if(isDemo){
setTimeout(function(){
state.resultImg=state.userPreview;state.score=88;state.scoreLabel='Excellent Match';
state.colorNote='The deep tones complement your complexion perfectly';
state.fitNote='Silhouette aligns well with your body proportions';
state.styleNote='Clean and elegant choice for any occasion';
state.recommendations=[];state.step=3;renderModal();
},4000);
return;
}

var fd=new FormData();
fd.append('user_image',state.userFile);
fd.append('product_image_url',state.productImg);
fd.append('product_id',state.productId||'');
fd.append('garment_description','');

fetch(BASE_URL+'/widget/tryon-and-rate',{method:'POST',headers:{'X-API-Key':API_KEY},body:fd})
.then(function(r){if(!r.ok)throw new Error('Request failed');return r.json();})
.then(function(data){
state.resultImg=data.result_image_url;state.score=data.score;state.scoreLabel=data.score_label;
state.colorNote=data.color_note;state.fitNote=data.fit_note;state.styleNote=data.style_note;
state.recommendations=data.recommended_products||[];state.step=3;renderModal();
})
.catch(function(err){
console.error('FitSnap widget error:',err);
state.step=1;renderModal();
var body=document.querySelector('.fitsnap-body');
if(body){var e=document.createElement('div');e.className='fitsnap-error';e.textContent='Something went wrong, please try again';body.prepend(e);}
});
}

function loadProducts(){
if(isDemo||!API_KEY)return;
fetch(BASE_URL+'/widget/brand-products',{headers:{'X-API-Key':API_KEY}})
.then(function(r){return r.json();})
.then(function(data){state.products=data.products||[];})
.catch(function(){});
}

function init(){
injectStyles();
state.productImg=detectProductImage();
loadProducts();
var btn=document.createElement('button');btn.className='fitsnap-widget fitsnap-trigger';btn.innerHTML='👗 Try On';btn.onclick=openModal;
document.body.appendChild(btn);
}

if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded',init);}else{init();}
})();
