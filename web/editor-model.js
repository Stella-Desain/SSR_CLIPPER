/* Native template helpers: output coordinates and time never depend on preview size. */
(function(root, factory) {
  const model = factory();
  if (typeof module === 'object' && module.exports) module.exports = model;
  if (root) root.EditorModel = model;
})(typeof window !== 'undefined' ? window : null, function() {
  'use strict';
  const copy = value => JSON.parse(JSON.stringify(value));
  const clamp = (value, min, max) => Math.max(min, Math.min(max, Number(value) || 0));
  const ratios = {'9:16':[1080,1920], '1:1':[1080,1080], '16:9':[1920,1080]};
  const uid = () => 'layer-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2,9);
  function ratio(canvas) {
    const value = canvas.width / canvas.height;
    return value < .8 ? '9:16' : value > 1.4 ? '16:9' : '1:1';
  }
  function interval(timing = {}, duration = 30) {
    duration = Math.max(0, Number(duration) || 0);
    const length = Math.max(0, Number(timing.duration) || 0);
    const offset = Math.max(0, Number(timing.start) || 0);
    let start = 0, end = duration;
    if (timing.mode === 'start') {start = offset; end = start + length;}
    else if (timing.mode === 'end') {end = duration - offset; start = end - length;}
    else if (timing.mode === 'percent') {start = duration * offset / 100; end = start + duration * length / 100;}
    return {start:clamp(start,0,duration), end:clamp(end,0,duration)};
  }
  function visibleAt(layer, time, duration) {
    if (layer.visible === false) return false;
    const range = interval(layer.timing, duration);
    return range.end > range.start && time >= range.start && (time < range.end || (time === duration && range.end === duration));
  }
  function layer(type, canvas, extra = {}) {
    const w = canvas.width, h = canvas.height;
    const base = {id:uid(), type, name:{text:'Teks',subtitle:'Subtitle',video:'Sumber video',rect:'Bingkai',image:'Gambar'}[type],
      x:w*.1,y:h*.1,width:w*.8,height:h*.12,rotation:0,visible:true,locked:false,timing:{mode:'full',start:0,duration:4}};
    if (type === 'video') Object.assign(base,{x:0,y:0,width:w,height:h,fit:'cover',framing:'fit'});
    if (type === 'text' || type === 'subtitle') Object.assign(base,{font_family:'Arial',font_size:Math.round(w*.055),color:'#ffffff',align:'center',bold:true,outline_color:'#000000',outline_width:2});
    if (type === 'text') Object.assign(base,{binding:'static',text:'Teks Anda',timing:{mode:'start',start:0,duration:4}});
    if (type === 'subtitle') Object.assign(base,{y:h*.72,height:h*.18,words_per_group:4,max_lines:2,highlight_color:'#bcff32',background:'#00000000'});
    if (type === 'rect') Object.assign(base,{color:'#101820',border_color:'#ffffff',border_width:2});
    if (type === 'image') Object.assign(base,{width:w*.25,height:w*.25,asset_id:'',fit:'contain'});
    return Object.assign(base, extra);
  }
  function resizeCanvas(project, newRatio) {
    if (!ratios[newRatio]) throw Error('Rasio tidak didukung.');
    const [width,height] = ratios[newRatio], xScale = width/project.canvas.width, yScale = height/project.canvas.height;
    for (const item of project.layers) {
      item.x *= xScale; item.y *= yScale; item.width *= xScale; item.height *= yScale;
      if (item.font_size) item.font_size = Math.max(8, Math.round(item.font_size*xScale));
    }
    project.canvas.width = width; project.canvas.height = height;
    return project;
  }
  function parseSrt(text) {
    const seconds = timestamp => {const parts=timestamp.trim().replace(',', '.').split(':').map(Number);return parts.length===3 ? parts[0]*3600+parts[1]*60+parts[2] : NaN;};
    return String(text || '').replace(/\r/g,'').trim().split(/\n\s*\n/).map(block => {
      const lines=block.split('\n'), index=lines.findIndex(line=>line.includes('-->'));
      if(index<0)return null;
      const times=lines[index].split('-->'), start=seconds(times[0]),end=seconds(times[1].split(/\s+/).filter(Boolean)[0]);
      return {start,end,text:lines.slice(index+1).join(' ').replace(/<[^>]*>/g,'')};
    }).filter(cue=>cue && Number.isFinite(cue.start) && Number.isFinite(cue.end) && cue.end>cue.start);
  }
  function subtitleAt(cues, time, groupSize = 4) {
    const cue=cues.find(c=>time>=c.start && time<c.end);
    if(!cue)return '';
    const words=cue.text.trim().split(/\s+/), count=Math.max(1,Number(groupSize)||4);
    const word=Math.min(words.length-1,Math.floor((time-cue.start)/(cue.end-cue.start)*words.length));
    const start=Math.floor(word/count)*count;
    return words.slice(start,start+count).join(' ');
  }
  function wrapTokens(tokens, layer) {
    const budget=Math.max(2,Math.floor(layer.width/(layer.font_size*.58))),lines=[];let current=[],count=0;
    for(let i=0;i<tokens.length;i++){const size=tokens[i].length;if(current.length&&count+size+1>budget){lines.push(current);current=[];count=0;}current.push(i);count+=size+(current.length>1?1:0);}
    if(current.length)lines.push(current);return lines;
  }
  function subtitleFrame(cues,time,layer) {
    const words=[];
    for(const cue of cues){const tokens=String(cue.text||cue.word||'').trim().split(/\s+/).filter(Boolean);for(let i=0;i<tokens.length;i++)words.push({word:tokens[i],start:cue.start+(cue.end-cue.start)*i/tokens.length,end:cue.start+(cue.end-cue.start)*(i+1)/tokens.length});}
    words.sort((a,b)=>a.start-b.start);let index=0;
    while(index<words.length){let group=words.slice(index,index+(layer.words_per_group||4));for(let gap=1;gap<group.length;gap++)if(group[gap].start-group[gap-1].end>.8){group=group.slice(0,gap);break;}
      while(group.length>1&&wrapTokens(group.map(w=>w.word),layer).length>(layer.max_lines||2))group=group.slice(0,-1);
      for(let active=0;active<group.length;active++){const word=group[active],end=group[active+1]?.start??word.end;if(time>=word.start&&time<end){const tokens=group.map(w=>w.word);return {tokens,lines:wrapTokens(tokens,layer),active};}}
      index+=group.length;
    }return {tokens:[],lines:[],active:-1};
  }
  function safeGuide(platform, canvas) {
    const w=canvas.width,h=canvas.height;
    // Conservative guides, not a guarantee against platform UI variations.
    return platform==='instagram' ? {x:w*.08,y:h*.12,width:w*.8,height:h*.66} : {x:w*(60/540),y:h*(126/960),width:w*(360/540),height:h*(514/960)};
  }
  function assetURL(value) {
    const url=String(value || '');
    return /^(https?:|file:|data:image\/|blob:)/i.test(url) ? url : '';
  }
  function History(limit=60) {
    this.past=[];this.future=[];this.limit=limit;
  }
  History.prototype.push=function(project){this.past.push(copy(project));if(this.past.length>this.limit)this.past.shift();this.future=[];};
  function preserveRegistry(value,project){for(const key of ['revision','assets','published_versions','created_at','updated_at','archived','last_render'])if(project[key]!==undefined)value[key]=copy(project[key]);return value;}
  History.prototype.undo=function(project){if(!this.past.length)return null;this.future.push(copy(project));return preserveRegistry(this.past.pop(),project);};
  History.prototype.redo=function(project){if(!this.future.length)return null;this.past.push(copy(project));return preserveRegistry(this.future.pop(),project);};
  return {copy,clamp,ratios,ratio,interval,visibleAt,layer,resizeCanvas,parseSrt,subtitleAt,wrapTokens,subtitleFrame,safeGuide,assetURL,History};
});
