/* All displayed times use one configured zone and an explicit 12-hour clock. */
(() => {
  let zone='Asia/Makassar';
  const pad=value=>String(value).padStart(2,'0');
  function configure(value){new Intl.DateTimeFormat('en-US',{timeZone:value}).format();zone=value;}
  function label(){return ({'Asia/Makassar':'WITA','Asia/Jakarta':'WIB','Asia/Jayapura':'WIT'})[zone] || zone;}
  function parts(value){
    // Legacy timestamps without an offset are already local wall time.
    const naive=typeof value==='string'&&value.match(/^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::\d{2}(?:\.\d+)?)?)?$/);
    if(naive)return {year:naive[1],month:naive[2],day:naive[3],hour:naive[4]||'00',minute:naive[5]||'00'};
    const date=new Date(value);if(Number.isNaN(date.getTime()))return null;
    return Object.fromEntries(new Intl.DateTimeFormat('en-GB',{timeZone:zone,year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(date).map(p=>[p.type,p.value]));
  }
  function clock(value){const [h,m]=String(value).split(':').map(Number);return `${pad(h%12||12)}:${pad(m)} ${h>=12?'PM':'AM'}`;}
  function date(value){const p=parts(value);return p?`${p.day}/${p.month}/${p.year}`:'Waktu belum tersedia';}
  function format(value){const p=parts(value);return p?`${date(value)}, ${clock(p.hour+':'+p.minute)} ${label()}`:'Waktu belum tersedia';}
  function clockInput(value='09:00',name='Jam upload'){
    const element=document.createElement('span');element.className='wf-clock-input';
    const hour=document.createElement('select'),minute=document.createElement('select'),period=document.createElement('select');
    for(const [input,suffix] of [[hour,'jam'],[minute,'menit'],[period,'AM/PM']]){input.className='select';input.setAttribute('aria-label',`${name}, ${suffix}`);}
    for(let i=1;i<=12;i++)hour.add(new Option(pad(i),String(i)));
    for(let i=0;i<60;i++)minute.add(new Option(pad(i),pad(i)));
    for(const p of ['AM','PM'])period.add(new Option(p,p));
    function set(v){const [h,m]=v.split(':').map(Number);hour.value=String(h%12||12);minute.value=pad(m);period.value=h>=12?'PM':'AM';}
    function get(){return pad(Number(hour.value)%12+(period.value==='PM'?12:0))+':'+minute.value;}
    set(value);element.append(hour,document.createTextNode(':'),minute,period);
    return {element,inputs:[hour,minute,period],get,set};
  }
  window.SSRTime={configure,label,parts,format,date,clock,clockInput,get timezone(){return zone;}};
})();
