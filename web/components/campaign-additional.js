/* Final template ratios; never starts authoring editors or installs models. */
window.Components.CampaignAdditionalEditor = function(host, api) {
  let items=[], presets=[], generation=0, pending=0, sequence=0;
  const previews=new Map();
  const uploading=new Set(), messages=new Map(), previewRatios=new Map();
  const maxImages=24;
  const imageId=()=> 'image-'+Date.now().toString(36)+'-'+(++sequence);
  const defaultLayout=()=>({x:.65,y:.18,width:.18,opacity:1});
  function migrateImages(item){
    if(item.type!=='watermark')return;
    if(!Object.hasOwn(item,'images'))item.images=item.image?.path?[{id:item.id,image:item.image,layout:item.layout || defaultLayout()}]:[];
    for(const layer of item.images){layer.id ||= imageId();layer.layout ||= defaultLayout();layer.layout.opacity=1;}
    delete item.image;delete item.layout;
  }
  const el=(tag,text,cls)=>{const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(cls)node.className=cls;return node;};
  const header=el('div',undefined,'wf-additional-header'), title=el('h3','Additional');
  const add=el('button','Tambah','btn btn-outline');add.type='button';add.setAttribute('aria-expanded','false');
  const chooser=el('div',undefined,'wf-additional-chooser');chooser.hidden=true;
  const list=el('div',undefined,'wf-additional-list');
  header.append(title,add);host.append(header,chooser,list);
  add.onclick=()=>{chooser.hidden=!chooser.hidden;add.setAttribute('aria-expanded',String(!chooser.hidden));};
  for(const [type,name] of [['watermark','Watermark'],['face_filter','Hanya clip wajah']]){
    const button=el('button',name,'btn btn-outline');button.type='button';button.dataset.additionalType=type;
    button.onclick=()=>{items.push({id:'additional-'+Date.now().toString(36)+'-'+(++sequence),type,enabled:true,ratios:['9:16'],
      platforms:['tiktok','instagram'],template_scope:'all',template_ids:[],
      ...(type==='watermark'?{images:[]}:{image:{}})});chooser.hidden=true;add.setAttribute('aria-expanded','false');render();};
    chooser.append(button);
  }
  function ratios(){
    const options=new Set(['9:16','1:1','16:9']);
    const gcd=(a,b)=>b?gcd(b,a%b):a;
    for(const preset of presets){const c=preset.external_template?.canvas || preset.canvas;
      if(c?.width&&c?.height){const divisor=gcd(c.width,c.height);options.add(`${c.width/divisor}:${c.height/divisor}`);}}
    for(const item of items)for(const ratio of item.ratios || [])options.add(ratio);
    return [...options];
  }
  function render(){
    list.replaceChildren();
    if(!items.length){list.append(el('p','Tambahkan watermark atau foto orang yang harus muncul dalam highlight.','wf-template-intro'));return;}
    for(const item of items){
      migrateImages(item);
      item.platforms ||= ['tiktok','instagram'];item.template_scope ||= 'all';item.template_ids ||= [];
      const row=el('section',undefined,'wf-additional-item');row.dataset.additionalId=item.id;
      const name=item.type==='watermark'?'Watermark':'Hanya clip wajah';
      row.setAttribute('aria-label',name);
      const heading=el('div',undefined,'wf-additional-header'), enabledLabel=el('label',undefined,'wf-additional-enabled');
      const enabled=el('input');enabled.type='checkbox';enabled.checked=item.enabled;enabled.setAttribute('aria-label','Aktifkan '+name);
      enabled.onchange=()=>item.enabled=enabled.checked;
      enabledLabel.append(enabled,el('strong',name));
      const remove=el('button','Hapus','btn btn-outline');remove.type='button';remove.onclick=()=>{items=items.filter(value=>value!==item);render();};
      heading.append(enabledLabel,remove);row.append(heading);
      const fields=el('fieldset',undefined,'wf-additional-ratios');fields.append(el('legend','Berlaku untuk rasio hasil template'));
      for(const ratio of ratios()){
        const label=el('label'), input=el('input');input.type='checkbox';input.value=ratio;input.checked=item.ratios.includes(ratio);
        input.setAttribute('aria-label',name+' untuk '+ratio);
        input.onchange=()=>{item.ratios=input.checked?[...new Set([...item.ratios,ratio])]:item.ratios.filter(value=>value!==ratio);};
        label.append(input,document.createTextNode(' '+ratio));fields.append(label);
      }
      row.append(fields);
      const social=el('fieldset',undefined,'wf-additional-ratios');social.append(el('legend','Berlaku untuk sosmed'));
      for(const [platform,labelText] of [['tiktok','TikTok'],['instagram','IG']]){
        const label=el('label'),check=el('input');check.type='checkbox';check.value=platform;check.checked=item.platforms.includes(platform);
        check.setAttribute('aria-label',name+' untuk '+labelText);check.dataset.platform=platform;
        check.onchange=()=>{item.platforms=check.checked?[...new Set([...item.platforms,platform])]:item.platforms.filter(value=>value!==platform);};
        label.append(check,document.createTextNode(' '+labelText));social.append(label);
      }
      const scopeLabel=el('label','Penggunaan pada template','wf-field'),scope=el('select',undefined,'select');scope.setAttribute('aria-label','Penggunaan Additional pada template');
      for(const [value,text] of [['all','Semua template'],['include','Hanya digunakan pada template'],['exclude','Tidak digunakan pada template']]){const option=el('option',text);option.value=value;scope.append(option);}
      scope.value=item.template_scope;scopeLabel.append(scope);
      const templateChoices=el('fieldset',undefined,'wf-additional-templates');templateChoices.append(el('legend','Pilih template'));templateChoices.hidden=item.template_scope==='all';
      for(const preset of presets){
        const label=el('label'),check=el('input');check.type='checkbox';check.value=preset.id;check.checked=item.template_ids.includes(preset.id);check.dataset.templateId=preset.id;check.setAttribute('aria-label',name+' pada '+preset.name);
        check.onchange=()=>{item.template_ids=check.checked?[...new Set([...item.template_ids,preset.id])]:item.template_ids.filter(value=>value!==preset.id);};label.append(check,el('span',preset.name));templateChoices.append(label);
      }
      scope.onchange=()=>{item.template_scope=scope.value;templateChoices.hidden=scope.value==='all';};
      row.append(social,scopeLabel,templateChoices);
      const watermark=item.type==='watermark';
      const uploadRow=el('div',undefined,'wf-additional-upload'), upload=el('button',watermark?'Tambah gambar':item.image?.path?'Ganti gambar':'Unggah gambar','btn btn-outline');upload.type='button';
      const filename=el('span',watermark?`${item.images.length}/${maxImages} gambar`:item.image?.name || 'Belum ada gambar');
      const savedMessage=messages.get(item.id);
      const message=el('p',savedMessage?.text || (uploading.has(item.id)?'Memeriksa gambar…':''),'wf-additional-status');message.setAttribute('role','status');
      if(savedMessage?.error)message.classList.add('wf-error');upload.disabled=uploading.has(item.id)||(watermark&&item.images.length>=maxImages);
      const image=el('img');image.alt=item.type==='watermark'?'Preview watermark':'Foto wajah target';image.hidden=true;
      image.className='wf-additional-photo';
      uploadRow.append(upload,filename);row.append(uploadRow);
      function cachePreview(result){previews.set(result.sha256,result);if(previews.size>128)previews.delete(previews.keys().next().value);}
      function loadPreview(asset,stillPresent,show){
        if(!asset?.path)return;
        const cached=previews.get(asset.sha256);if(cached){show(cached);return;}
        const version=generation,hash=asset.sha256;
        Promise.resolve(api().get_additional_image_preview(asset)).then(result=>{
          if(version!==generation||!items.includes(item)||!stillPresent()||asset.sha256!==hash)return;
          if(result.status==='ok'){cachePreview(result);show(result);}else{message.textContent=result.message;message.classList.add('wf-error');}
        }).catch(error=>{if(version===generation&&items.includes(item)&&stillPresent()){message.textContent=String(error);message.classList.add('wf-error');}});
      }
      if(watermark){
        const previewLabel=el('label','Preview tata letak','wf-field'), previewRatio=el('select',undefined,'select');previewRatio.setAttribute('aria-label','Rasio preview watermark');
        for(const ratio of ratios()){const option=el('option',ratio);option.value=ratio;previewRatio.append(option);}previewRatio.value=previewRatios.get(item.id) || item.ratios[0] || '9:16';
        previewLabel.append(previewRatio);
        const canvas=el('div',undefined,'wf-watermark-canvas');canvas.setAttribute('aria-label','Posisi watermark pada hasil template');
        const guide=el('img',undefined,'wf-watermark-guide');guide.src='assets/tiktok-safe-area.png';guide.alt='Panduan safe area TikTok dari referensi';guide.draggable=false;
        canvas.append(guide);
        const imageList=el('ul',undefined,'wf-watermark-images'),updates=[];
        const removeImage=layer=>{
          const index=item.images.indexOf(layer);if(index<0)return;
          item.images.splice(index,1);messages.set(item.id,{text:'Gambar dihapus. Simpan campaign untuk menerapkannya.',error:false});render();
          const current=[...list.querySelectorAll('.wf-additional-item')].find(node=>node.dataset.additionalId===item.id);
          const next=current?.querySelectorAll('.wf-watermark-box')[Math.min(index,item.images.length-1)];
          (next || current?.querySelector('.wf-additional-upload button'))?.focus?.();
        };
        function trashButton(layer,cls){
          const button=el('button',undefined,cls);button.type='button';button.title='Hapus gambar';button.setAttribute('aria-label','Hapus gambar '+(layer.image.name || 'watermark'));
          button.innerHTML='<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7M14 10v7"/></svg>';
          button.onpointerdown=event=>event.stopPropagation();button.onkeydown=event=>event.stopPropagation();
          button.onclick=event=>{event.stopPropagation();removeImage(layer);};return button;
        }
        for(const layer of item.images){
        const box=el('div',undefined,'wf-watermark-box');box.hidden=true;box.tabIndex=0;box.dataset.watermarkImage=layer.id;box.setAttribute('role','group');box.setAttribute('aria-label',(layer.image.name || 'Watermark')+': geser untuk memindahkan, tarik sudut untuk mengubah ukuran');
        const logo=el('img');logo.alt='Posisi watermark';logo.draggable=false;
        const handle=el('button',undefined,'wf-watermark-resize');handle.type='button';handle.setAttribute('aria-label','Ubah ukuran watermark');
        box.append(logo,handle,trashButton(layer,'wf-watermark-delete'));canvas.append(box);
        const file=el('li',undefined,'wf-watermark-file');file.append(el('span',layer.image.name || 'Gambar watermark'),trashButton(layer,'wf-watermark-file-delete'));imageList.append(file);
        let geometry={fw:.18,fh:.1,left:0,top:0,ratio:9/16,imageRatio:1};
        const clamp=(value,low,high)=>Math.max(low,Math.min(high,value));
        function setGeometry(width,left,top){
          const fw=clamp(width,.01,Math.min(1,geometry.imageRatio/geometry.ratio)),fh=fw*geometry.ratio/geometry.imageRatio;
          layer.layout.width=fw;layer.layout.x=clamp(left/Math.max(.00001,1-fw),0,1);layer.layout.y=clamp(top/Math.max(.00001,1-fh),0,1);updatePreview();
        }
        const updatePreview=()=>{
          const [w,h]=previewRatio.value.split(':').map(Number);canvas.style.aspectRatio=`${w} / ${h}`;
          canvas.style.width=`min(100%, ${Math.min(360,640*w/h)}px)`;guide.hidden=previewRatio.value!=='9:16';
          const asset=previews.get(layer.image.sha256), imageRatio=(asset?.width || layer.image.width || 1)/(asset?.height || layer.image.height || 1);
          const fraction=Math.max(.01,Math.min(1,layer.layout.width));
          const fw=Math.min(fraction,imageRatio*h/w), fh=fw*w/h/imageRatio;
          geometry={fw,fh,left:clamp(layer.layout.x,0,1)*(1-fw),top:clamp(layer.layout.y,0,1)*(1-fh),ratio:w/h,imageRatio};
          box.style.cssText=`width:${fw*100}%;height:${fh*100}%;left:${geometry.left*100}%;top:${geometry.top*100}%;`;
          if(asset){logo.src=asset.preview_url;box.hidden=false;}
        };
        let dragging=null;
        const startDrag=(event,resize)=>{if(event.button!==undefined&&event.button!==0)return;event.preventDefault();event.stopPropagation();box.focus?.();dragging={...geometry,x:event.clientX,y:event.clientY,resize};box.setPointerCapture?.(event.pointerId);};
        box.onpointerdown=event=>{if(event.button!==undefined&&event.button!==0)return;startDrag(event,false);};handle.onpointerdown=event=>startDrag(event,true);
        box.onpointerup=()=>dragging=null;box.onpointercancel=()=>dragging=null;box.onlostpointercapture=()=>dragging=null;
        box.onpointermove=event=>{
          if(!dragging)return;
          const bounds=canvas.getBoundingClientRect();
          if(!bounds.width||!bounds.height)return;
          const dx=(event.clientX-dragging.x)/bounds.width,dy=(event.clientY-dragging.y)/bounds.height;
          if(dragging.resize){const delta=Math.abs(dx)>Math.abs(dy*geometry.imageRatio/geometry.ratio)?dx:dy*geometry.imageRatio/geometry.ratio;
            setGeometry(clamp(dragging.fw+delta,.01,Math.min(1-dragging.left,(1-dragging.top)*geometry.imageRatio/geometry.ratio)),dragging.left,dragging.top);
          }else setGeometry(dragging.fw,dragging.left+dx,dragging.top+dy);
        };
        box.onkeydown=event=>{
          if(event.target&&event.target!==box)return;
          const step=event.shiftKey ? .03 : .005;
          if(['+','=','-'].includes(event.key)){event.preventDefault();setGeometry(geometry.fw+(event.key==='-'?-step:step),geometry.left,geometry.top);}
          else if(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(event.key)){event.preventDefault();setGeometry(geometry.fw,geometry.left+({'ArrowLeft':-step,'ArrowRight':step}[event.key] || 0),geometry.top+({'ArrowUp':-step,'ArrowDown':step}[event.key] || 0));}
        };
        updates.push(updatePreview);updatePreview();
        loadPreview(layer.image,()=>item.images.includes(layer),updatePreview);
        }
        function updateCanvas(){const [w,h]=previewRatio.value.split(':').map(Number);canvas.style.aspectRatio=`${w} / ${h}`;canvas.style.width=`min(100%, ${Math.min(360,640*w/h)}px)`;guide.hidden=previewRatio.value!=='9:16';updates.forEach(update=>update());}
        previewRatio.onchange=()=>{previewRatios.set(item.id,previewRatio.value);updateCanvas();};updateCanvas();
        row.append(previewLabel,canvas,imageList,el('p','Pilih beberapa gambar sekaligus atau tekan Tambah gambar lagi. Geser setiap gambar, tarik sudut untuk ukuran, dan tekan ikon sampah di kiri atas untuk menghapusnya. Keyboard: panah untuk posisi, +/− untuk ukuran. Panduan TikTok tidak masuk ke video.','wf-template-intro'));
      }else{
        row.append(image,el('p','Unggah foto dengan satu wajah yang jelas. Highlight harus menampilkan orang yang sama pada minimal 20% sampel, dengan beberapa kecocokan terpisah. Beberapa foto target berlaku sebagai pilihan: cukup salah satunya muncul.','wf-template-intro'));
        loadPreview(item.image,()=>!!item.image?.path,result=>{image.src=result.preview_url;image.hidden=false;});
      }
      row.append(message);list.append(row);
      upload.onclick=async()=>{
        if(uploading.has(item.id))return;
        const version=generation;pending++;uploading.add(item.id);upload.disabled=true;message.textContent='Memeriksa gambar…';message.classList.remove('wf-error');messages.delete(item.id);
        try{
          const result=watermark?await api().browse_additional_images():await api().browse_additional_image(item.type);
          if(version!==generation||!items.includes(item))return;
          if(result.status==='cancelled'){message.textContent='';messages.delete(item.id);return;}
          if(result.status!=='ok')throw Error(result.message || 'Gambar belum dapat ditambahkan.');
          let count=1;
          if(watermark){
            const selections=result.images || [],remaining=maxImages-item.images.length;
            if(selections.length>remaining)throw Error(`Tersisa ${remaining} slot gambar. Pilih paling banyak ${remaining} gambar lagi.`);
            if(!selections.length)throw Error('Belum ada gambar yang dapat ditambahkan.');
            selections.forEach(selection=>{const offset=item.images.length%6;cachePreview(selection);item.images.push({id:imageId(),image:structuredClone(selection.image),layout:{...defaultLayout(),x:.65+offset*.04,y:.18+offset*.04}});});count=selections.length;
          }else{item.image=structuredClone(result.image);cachePreview(result);}
          const rejected=result.errors?.length?` ${result.message || 'Sebagian gambar tidak dapat dibaca.'}`:'';
          messages.set(item.id,{text:`${count} gambar ditambahkan. Simpan campaign untuk menerapkannya.${rejected}`,error:!!rejected});
        }catch(error){if(version===generation&&items.includes(item)){message.textContent=String(error);message.classList.add('wf-error');messages.set(item.id,{text:message.textContent,error:true});}}
        finally{if(version===generation){pending--;uploading.delete(item.id);render();}}
      };
    }
  }
  return {
    setValue(value=[], available=[]){generation++;pending=0;add.disabled=false;uploading.clear();messages.clear();previewRatios.clear();items=structuredClone(value);presets=available;render();},
    setPresets(available){presets=available;render();},
    invalidate(){generation++;pending=0;add.disabled=true;uploading.clear();messages.clear();previewRatios.clear();items=[];chooser.hidden=true;list.replaceChildren(el('p','Memuat Additional…','wf-template-intro'));},
    getValue(){if(pending)throw Error('Tunggu pemeriksaan gambar Additional selesai, lalu simpan campaign.');return structuredClone(items);},
  };
};
