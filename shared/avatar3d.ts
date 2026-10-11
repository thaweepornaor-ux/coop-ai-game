import * as G from './avatar3d-engine';
import { AVATAR_OPTIONS } from './avatar.js';
import { characterFor } from './characters';

// Geometry is authored as continuous sampled surfaces, not assembled SVG shapes.
function surface(fn:(u:number,v:number)=>number[],w=24,h=16){
 const g=new G.BufferGeometry();const normals:number[]=[];
 const p=(u:number,v:number)=>fn(u,v);
 const normal=(u:number,v:number)=>{const a=p(u+.0001,v),b=p(u-.0001,v),c=p(u,Math.min(.9999,v+.0001)),d=p(u,Math.max(.0001,v-.0001));const x=a.map((n,i)=>n-b[i]),y=c.map((n,i)=>n-d[i]);const n=[x[1]*y[2]-x[2]*y[1],x[2]*y[0]-x[0]*y[2],x[0]*y[1]-x[1]*y[0]],l=Math.hypot(...n)||1;return n.map(n=>n/l);};
 for(let j=0;j<h;j++)for(let i=0;i<w;i++){const a=[i/w,j/h],b=[(i+1)/w,j/h],c=[(i+1)/w,(j+1)/h],d=[i/w,(j+1)/h];for(const t of [[a,d,c],[a,c,b]]){g.triangle(...t.map(q=>p(q[0],q[1])) as [number[],number[],number[]]);for(const q of t)normals.push(...normal(q[0],q[1]));}}
 g.normals=normals;return g;
}
// Cubic anatomical profiles; rings follow the full 3D tangent, including elbow flexion.
function cubic(values:number[],v:number){const f=Math.max(0,Math.min(.999999,v))*(values.length-1),i=Math.floor(f),t=f-i,a=values[Math.max(0,i-1)],b=values[i],c=values[i+1],d=values[Math.min(values.length-1,i+2)];return .5*(2*b+(-a+c)*t+(2*a-5*b+4*c-d)*t*t+(-a+3*b-3*c+d)*t*t*t);}
function sweep(path:number[][],radii:number[],depth=1){
 const curve=(v:number)=>[0,1,2].map(k=>cubic(path.map(p=>p[k]),v));
 const ring=(u:number,v:number)=>{const c=curve(v),a=curve(Math.max(0,v-.0001)),b=curve(Math.min(1,v+.0001)),t=b.map((n,k)=>n-a[k]),len=Math.hypot(...t)||1;for(let k=0;k<3;k++)t[k]/=len;const side=[-t[1],t[0],0],sl=Math.hypot(...side)||1;for(let k=0;k<3;k++)side[k]/=sl;const bin=[t[1]*side[2]-t[2]*side[1],t[2]*side[0]-t[0]*side[2],t[0]*side[1]-t[1]*side[0]],r=Math.max(.001,cubic(radii,v)),angle=u*Math.PI*2;return c.map((n,k)=>n+side[k]*Math.cos(angle)*r+bin[k]*Math.sin(angle)*r*depth);};
 const g=surface(ring,28,36);for(const v of [0,1]){const c=curve(v);for(let j=0;j<28;j++)g.triangle(c,ring(j/28,v),ring((j+1)/28,v));}return g;
}
// One smooth implicit surface joins wrist, palm, knuckles, four curved fingers and thumb.
let handGeometry:G.BufferGeometry|undefined;
function sculptHand(){if(handGeometry)return handGeometry;
 const ellipse=(p:number[],c:number[],r:number[])=>{const d=p.map((v,k)=>(v-c[k])/r[k]);return (Math.hypot(...d)-1)*Math.min(...r);};
 const union=(a:number,b:number,k=.013)=>{const h=Math.max(0,Math.min(1,.5+.5*(b-a)/k));return b*(1-h)+a*h-k*h*(1-h);};
 const field=(p:number[])=>{let d=ellipse(p,[0,0,0],[.067,.087,.035]);d=union(d,ellipse(p,[0,.09,-.008],[.063,.068,.045]));for(let f=0;f<4;f++){const x=-.044+f*.029,y=-.105-(f===1?.021:f===2?.014:0);d=union(d,ellipse(p,[x,y,.014],[.017,.061-(f===3?.012:0),.023]),.014);d=union(d,ellipse(p,[x,y-.032,.025],[.016,.030,.019]),.010);}d=union(d,ellipse(p,[.070,-.005,.01],[.024,.058,.030]),.020);return union(d,ellipse(p,[.074,-.045,.035],[.024,.035,.025]),.015);};
 const g=new G.BufferGeometry(),min=[-.095,-.20,-.06],step=.013,n=[16,28,11],off=[[0,0,0],[1,0,0],[1,1,0],[0,1,0],[0,0,1],[1,0,1],[1,1,1],[0,1,1]],tet=[[0,5,1,6],[0,1,2,6],[0,2,3,6],[0,3,7,6],[0,7,4,6],[0,4,5,6]],edges=[[0,1],[0,2],[0,3],[1,2],[1,3],[2,3]];
 const normal=(p:number[])=>{const e=.0002,d=[0,1,2].map(k=>{const a=[...p],b=[...p];a[k]+=e;b[k]-=e;return field(a)-field(b);}),l=Math.hypot(...d)||1;return d.map(v=>v/l);};
 for(let z=0;z<n[2];z++)for(let y=0;y<n[1];y++)for(let x=0;x<n[0];x++){const pos=off.map(o=>o.map((v,k)=>min[k]+([x,y,z][k]+v)*step)),ds=pos.map(field);if(ds.every(v=>v>0)||ds.every(v=>v<0))continue;for(const t of tet){const hit:number[][]=[];for(const [a,b]of edges){const i=t[a],j=t[b];if((ds[i]<0)===(ds[j]<0))continue;const w=ds[i]/(ds[i]-ds[j]);hit.push(pos[i].map((v,k)=>v+(pos[j][k]-v)*w));}if(hit.length<3)continue;const add=(a:number[],b:number[],c:number[])=>{g.triangle(a,b,c);g.normals.splice(g.normals.length-9,9,...normal(a),...normal(b),...normal(c));};add(hit[0],hit[1],hit[2]);if(hit.length===4)add(hit[1],hit[3],hit[2]);}}
 return handGeometry=g;
}
export function createCharacter(input:Record<string,unknown>){
 const preset=characterFor(input.presetId||input.bodyStyle);
 const values:Record<string,any>={};const effective:Record<string,unknown>={...preset,...input};
 for(const [key,list]of Object.entries(AVATAR_OPTIONS))values[key]=list.find((o:any)=>o.value===effective[key])||list[0];
 const root=new G.Group();root.rig=new G.CharacterRig();const female=input.bodyStyle?values.bodyStyle.value==='female':preset.gender==='female';
 const mat=(color:string,roughness=.84)=>new G.MeshStandardMaterial({color,roughness});
 const skin=mat(values.skinTone.color,.48),hair=mat(values.hairColor.color,.34),shirt=mat(values.shirtColor.color),bottom=mat(values.bottomColor.color),shoes=mat(values.shoeColor.color),hat=mat(values.hatColor.color),white=mat('#f5f2e9'),dark=mat('#242332'),lip=mat('#8f5651'),gold=mat('#ccb778',.3);
 const sphere=new G.SphereGeometry(1,24,18);let rigPart=0;
 const mesh=(g:G.BufferGeometry,m:G.Material)=>{const o=new G.Mesh(g,m);o.rigPart=rigPart;root.add(o);return o;};
 const ell=(m:G.Material,x:number,y:number,z:number,a:number,b:number,c:number)=>{const o=mesh(sphere,m);o.position.set(x,y,z);o.scale.set(a,b,c);return o;};
 const face=(m:G.Mesh)=>{m.faceOverlay=true;return m;};
 const tube=(points:number[][],radii:number[],m:G.Material,depth=1)=>mesh(sweep(points,radii,depth),m);
 const fw=preset.faceWidth||1,fl=preset.faceLength||1,eye=preset.eyeSize||1,nose=preset.noseSize||1;
 const centerY=2.85;rigPart=1;
 const head=surface((u,v)=>{const a=u*Math.PI*2,b=v*Math.PI,y=Math.cos(b),jaw=1-.07*Math.max(0,-y);const cheek=1+.08*Math.exp(-(((y+.18)/.3)**2));const x=Math.sin(b)*Math.cos(a)*.405*fw*jaw*cheek;let z=Math.sin(b)*Math.sin(a)*.34;const yy=y*.41*fl;const front=Math.max(0,Math.sin(a));z+=front*(Math.exp(-((x/.045)**2+((yy+.025)/.145)**2))*.038+Math.exp(-((x/.075)**2+((yy+.085)/.055)**2))*.055)*nose;z+=front*Math.exp(-(((Math.abs(x)-.225)/.09)**2+((yy+.13)/.085)**2))*.033;z+=front*Math.exp(-((x/.25)**2+((yy+.16)/.13)**2))*.02;return[x,centerY+yy,z];},40,28);mesh(head,skin).name="head";
 // Art-directed neckline, sloped shoulders, rib cage, waist and hem.
 rigPart=2;
 const torso=surface((u,v)=>{const y=cubic([2.37,2.34,2.29,2.23,2.08,1.88,1.66,1.43],v),a=u*Math.PI*2;
 const width=cubic(female?[.12,.23,.31,.335,.315,.285,.265,.300]:[.13,.25,.355,.39,.375,.35,.325,.335],v);
 const d=cubic(female?[.095,.12,.15,.18,.19,.165,.145,.19]:[.10,.13,.17,.19,.205,.20,.178,.19],v);
 const fold=.0035*Math.sin(a*9+v*16)*Math.sin(v*Math.PI)**2;
 return[Math.cos(a)*(width+fold),y,Math.sin(a)*(d+fold)+.013*Math.sin(v*Math.PI)];},48,40);mesh(torso,shirt);
 rigPart=2;tube([[0,2.52,-.012],[0,2.42,0],[0,2.32,0]],[.108,.113,.123],skin,.86);
 rigPart=2;
 // Ribbed collar follows the neckline rather than a floating disk.
 mesh(surface((u,v)=>{const a=u*Math.PI*2,b=v*Math.PI*2;return[Math.cos(a)*(.128+.010*Math.cos(b)),2.367+.009*Math.sin(b),Math.sin(a)*(.099+.010*Math.cos(b))];},40,8),shirt);
 for(const side of [-1,1]){
  rigPart=1;ell(skin,side*.403*fw,2.83,-.015,.076,.104,.051);ell(mat('#ba8677'),side*.430*fw,2.83,.015,.025,.059,.021);
  // Facial elements sit on the actual curved face surface and remain visible at all tones.
  const ex=side*.146*fw,ez=.34*Math.sqrt(Math.max(.1,1-(ex/(.405*fw))**2))+.016;
  ell(white,ex,2.887,ez,.078*eye,.054*eye,.030);ell(mat('#644936',.26),ex-side*.005,2.887,ez+.028,.040*eye,.042*eye,.012);ell(dark,ex-side*.005,2.887,ez+.039,.023*eye,.031*eye,.010);ell(white,ex-.016,2.905,ez+.049,.012,.014,.006);
  mesh(new G.TubeGeometry(new G.QuadraticBezierCurve3(new G.Vector3(ex-.079,3.005,ez-.005),new G.Vector3(ex,3.042,ez+.016),new G.Vector3(ex+.079,3.008,ez-.008)),20,.011,10),hair);
  const longSleeve=values.shirtStyle.value==='shirt'||values.shirtStyle.value==='jacket';
  rigPart=side<0?3:4;
  const armPath=[[side*.285,2.24,0],[side*.375,2.19,.005],[side*.435,2.05,.035],[side*.46,1.84,.13],[side*.475,1.68,.19],[side*.49,1.48,.235]];
  const armRadius=[.117,.126,.115,.095,.096,.063];
  tube(armPath,armRadius,skin,.84);
  tube(longSleeve?armPath.slice(0,6):armPath.slice(0,3).concat([[side*.449,1.975,.066]]),longSleeve?[.125,.134,.123,.106,.105,.071]:[.125,.134,.123,.106],shirt,.84);
  const hand=mesh(sculptHand(),skin);hand.name="hand";hand.position.set(side*.49,1.40,.235);hand.scale.set(side*.92,1,.95);hand.rotation.z=side*.08;
  rigPart=side<0?5:6;
  const legPath=[[side*.172,1.50,-.018],[side*.182,1.34,-.018],[side*.185,1.09,.006],[side*.178,.84,.068],[side*.18,.67,.048],[side*.20,.49,-.014],[side*.207,.29,-.002]];
  tube(legPath,values.bottomStyle.value==='skirt'?[.159,.145,.126,.095,.102,.083,.061]:[.166,.157,.143,.121,.128,.112,.091],values.bottomStyle.value==='skirt'?skin:bottom,.91);
  ell(shoes,side*.21,.183,.08,.135,.092,.224);ell(white,side*.21,.115,.093,.139,.031,.23);ell(shoes,side*.21,.23,-.02,.104,.079,.112);
  for(let l=0;l<3;l++)ell(white,side*.21,.267,.08+l*.04,.049,.006,.008);
 }
 rigPart=0;
 if(values.bottomStyle.value==='skirt')tube([[0,1.50,0],[0,1.33,0],[0,1.13,0],[0,.94,0]],[female?.304:.335,.325,.347,.354],bottom,.64);
 else tube([[0,1.43,0],[0,1.36,0],[0,1.30,0]],[female?.298:.33,.31,.285],bottom,.63);
 rigPart=2;
 const shirtStyle=values.shirtStyle.value;
 if(shirtStyle!=='tshirt'){
  for(const s of [-1,1]){
   const cg=new G.BufferGeometry();cg.triangle([s*.05,2.29,.133],[s*.15,2.25,.181],[s*.095,2.135,.2]);cg.normals=cg.vertices.map((_,i)=>i%3===2?1:0);mesh(cg,shirtStyle==='jacket'?white:shirt);
   if(shirtStyle==='jacket'){const lapel=new G.BufferGeometry();lapel.triangle([s*.11,2.25,.2],[s*.27,2.08,.22],[s*.065,1.72,.235]);lapel.triangle([s*.11,2.25,.2],[s*.065,1.72,.235],[s*.035,2.14,.23]);lapel.normals=lapel.vertices.map((_,i)=>i%3===2?1:0);mesh(lapel,shirt);ell(gold,s*.12,2.045,.254,.027,.036,.008);ell(shirt,s*.2,1.65,.205,.115,.029,.025);}
  }
  if(shirtStyle==='jacket')ell(white,0,1.96,.2,.11,.34,.012);
  for(let i=0;i<(shirtStyle==='polo'?2:5);i++)ell(white,.015,2.13-i*.14,.235,.016,.017,.012);
 }
 rigPart=1;const smile=new G.QuadraticBezierCurve3(new G.Vector3(-.118,2.683,.307),new G.Vector3(0,2.596,.366),new G.Vector3(.118,2.683,.307));face(mesh(new G.TubeGeometry(smile,16,.01,8),lip));face(ell(lip,0,2.645,.337,.092,.027,.020));face(ell(mat('#fff7e9'),0,2.651,.355,.072,.012,.007));face(ell(lip,0,2.623,.339,.071,.009,.009));for(const side of [-1,1])face(ell(mat('#aa806d'),side*.025,2.787,.439,.007,.004,.008));
 const originalHair=values.hairStyle.value;const h=({shoulder:'long',wavy:female?'long':'short',swept:'sidepart',pixie:'short',bun:'ponytail'} as Record<string,string>)[originalHair]||originalHair;
 if(h!=='bald'){
  const cap=surface((u,v)=>{const a=u*Math.PI*2,front=Math.max(0,Math.sin(a)),b=v*Math.PI*(.61-.26*front);let x=Math.sin(b)*Math.cos(a)*.425*fw,yy=2.85+Math.cos(b)*.43*fl,z=Math.sin(b)*Math.sin(a)*.365-.012;
   if(h!=='buzz'){yy+=.055*(1-v);if(h==='sidepart')yy+=.065*Math.sin(a+.5)*Math.sin(b)*(1-v);if(h==='curly')yy+=.042*Math.sin(a*9)*Math.sin(b*8);}
   const groove=h==='buzz'?0:.014*Math.sin(a*18+b*6)*Math.sin(b);x*=1+groove;z*=1+groove;return[x,yy,z];},64,32);mesh(cap,hair);
  if(['sidepart','swept','short','pixie'].includes(originalHair))for(let lock=0;lock<5;lock++){const x=-.27+lock*.105;tube([[x,3.19,.12],[x+.055,3.27,.19],[x+.10,3.22,.27],[x+.075,3.10,.30]],[.033,.042,.038,.005],hair,.65);}
  if(h==='long'||h==='bob'){
   const shell=surface((u,v)=>{const a=Math.PI*.90+u*Math.PI*1.20,y=3.04-v*(h==='long'?(originalHair==='shoulder'?.79:1.02):.48);const spread=.39+.027*Math.sin(v*Math.PI)+.011*Math.sin(u*24+v*4);return[Math.cos(a)*spread*fw,y,Math.sin(a)*.355-.015];},32,16);mesh(shell,hair);
  }
  if(originalHair==='bun')ell(hair,0,2.67,-.38,.135,.13,.12);
  else if(h==='ponytail')tube([[0,2.99,-.35],[.03,2.72,-.43],[.07,2.4,-.38]],[.105,.105,.06],hair);
 }
 if(preset.glasses)for(const s of [-1,1]){const curve=surface((u,v)=>{const a=u*Math.PI*2,b=v*Math.PI*2;return[s*.15*fw+Math.sign(Math.cos(a))*Math.abs(Math.cos(a))**(preset.glassesStyle==='square'?.38:1)*(.098+Math.cos(b)*.008),2.88+Math.sign(Math.sin(a))*Math.abs(Math.sin(a))**(preset.glassesStyle==='square'?.38:1)*((preset.glassesStyle==='oval'?.088:.105)+Math.cos(b)*.008),.355+Math.sin(b)*.008];},24,6);mesh(curve,mat(({charcoal:'#303943',black:'#202b32',brown:'#654532',silver:'#b9bfc4',gold:'#b99a5a'} as Record<string,string>)[preset.glassesColor]||'#5a493d',.3));}if(preset.glasses)ell(mat('#5a493d'),0,2.9,.357,.055,.008,.009);
 if(values.hairColor.value==='saltpepper'||preset.age>=55)for(const side of [-1,1])tube([[side*.37,3.09,.01],[side*.39,2.96,.09]],[.023,.01],mat('#b8b8b2',.34));
 if(preset.facialHair)for(const s of [-1,1])ell(hair,s*.05,2.695,.324,.063,.013,.018);
 if(preset.age>=50)for(const s of [-1,1])face(ell(lip,s*.265,2.82,.263,.027,.005,.006));
 const hs=values.hatStyle.value;
 if(hs==='cap'){ell(hat,0,3.22,-.02,.43,.14,.36);ell(hat,0,3.16,.32,.36,.03,.22);}
 if(hs==='bucket'){tube([[0,3.37,0],[0,3.17,0]],[.3,.38],hat,.9);ell(hat,0,3.16,0,.48,.033,.42);}
 if(hs==='beret'){ell(hat,-.04,3.27,0,.45,.12,.36).rotation.z=-.12;ell(hat,0,3.39,0,.016,.04,.016);}
 // Adult proportions: common head transform retains the distinct facial sculpt.
 for(const o of root.children)if(o instanceof G.Mesh&&o.rigPart===1){const factor=.85;o.position.set(o.position.x*factor,o.position.y*factor+2.78*(1-factor),o.position.z*factor);o.scale.set(o.scale.x*factor,o.scale.y*factor,o.scale.z*factor);}
 root.rotation.y=-.12;return root;
}
export function createStudio(canvas?:HTMLCanvasElement){const renderer=new G.WebGLRenderer({canvas,alpha:true,antialias:true,preserveDrawingBuffer:true});renderer.setPixelRatio(1);renderer.setSize(360,480,false);const scene=new G.Scene(),camera=new G.PerspectiveCamera();return{renderer,scene,camera};}
export function disposeCharacter(model:G.Group){const gs=new Set<G.BufferGeometry>(),ms=new Set<G.Material>();model.traverse(o=>{if(o instanceof G.Mesh){gs.add(o.geometry);ms.add(o.material);}});gs.forEach(g=>g.dispose());ms.forEach(m=>m.dispose());}
let studio:ReturnType<typeof createStudio>|undefined;
const cache=new Map<string,string>();
let queue:Promise<void>=Promise.resolve();
/** Thumbnail jobs are deliberately serialized to avoid simultaneous WebGL readbacks.
 * Callers can abort obsolete wardrobe selections before they enter the queue.
 */
export function renderThumbnail(options:Record<string,unknown>,signal?:AbortSignal):Promise<string>{
 const key=JSON.stringify(options);
 const cancelled=()=>{if(signal?.aborted)throw new DOMException('Thumbnail request cancelled','AbortError');};
 cancelled();
 if(cache.has(key))return Promise.resolve(cache.get(key)!);
 const task=queue.then(async()=>{
  cancelled();
  // Yield between expensive character builds so pointer/click events stay responsive.
  await new Promise<void>(resolve=>setTimeout(resolve,16));
  cancelled();
  if(cache.has(key))return cache.get(key)!;
  if(studio?.renderer.isContextLost){studio.renderer.dispose();studio=undefined;}
  studio ||=createStudio();
  const{renderer,scene,camera}=studio;
  await renderer.ready;
  cancelled();
  if(renderer.isContextLost){renderer.dispose();studio=undefined;throw Error('Thumbnail context lost');}
  const model=createCharacter(options);
  scene.add(model);
  try{
   renderer.render(scene,camera);
   if(renderer.isContextLost){renderer.dispose();studio=undefined;throw Error('Thumbnail context lost');}
   const url=renderer.domElement.toDataURL('image/webp',.88);
   cancelled();
   cache.set(key,url);
   // Data URLs can be large; keep the thumbnail cache bounded on mobile.
   if(cache.size>80)cache.delete(cache.keys().next().value!);
   return url;
  }finally{scene.remove(model);disposeCharacter(model);}
 });
 queue=task.then(()=>{},()=>{});
 return task;
}
