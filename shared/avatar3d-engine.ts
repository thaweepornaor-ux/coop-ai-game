// Small native WebGL geometry engine. No third-party assets or network dependency.
export const SRGBColorSpace=0,ACESFilmicToneMapping=0;
export class Vector3{constructor(public x=0,public y=0,public z=0){}set(x:number,y:number,z:number){this.x=x;this.y=y;this.z=z;return this;}}
export class Material{color:string;roughness:number;constructor(options:any={}){this.color=options.color||'#fff';this.roughness=options.roughness??.5;}dispose(){}}
export class MeshStandardMaterial extends Material{}
export class BufferGeometry{vertices:number[]=[];normals:number[]=[];colors:string[]=[];uvs:number[]=[];faceCard=-1;dispose(){}triangle(a:number[],b:number[],c:number[]){const u=b.map((v,i)=>v-a[i]),v=c.map((n,i)=>n-a[i]);const n=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]];const len=Math.hypot(...n)||1;for(const p of [a,b,c]){this.vertices.push(...p);this.normals.push(...n.map(x=>x/len));}}}
export class SphereGeometry extends BufferGeometry{constructor(r=1,w=24,h=16){super();const p=(a:number,b:number)=>[r*Math.sin(b)*Math.cos(a),r*Math.cos(b),r*Math.sin(b)*Math.sin(a)];for(let j=0;j<h;j++)for(let i=0;i<w;i++){let a=i*2*Math.PI/w,b=j*Math.PI/h,da=2*Math.PI/w,db=Math.PI/h;this.triangle(p(a,b),p(a,b+db),p(a+da,b+db));this.triangle(p(a,b),p(a+da,b+db),p(a+da,b));}this.normals=this.vertices.map(v=>v/r);}}
export class CylinderGeometry extends BufferGeometry{constructor(top:number,base:number,height:number,n=32){super();for(let i=0;i<n;i++){const a=i*Math.PI*2/n,b=(i+1)*Math.PI*2/n;const p=(r:number,y:number,t:number)=>[r*Math.cos(t),y,r*Math.sin(t)];this.triangle(p(top,height/2,a),p(base,-height/2,a),p(base,-height/2,b));this.triangle(p(top,height/2,a),p(base,-height/2,b),p(top,height/2,b));this.triangle([0,height/2,0],p(top,height/2,b),p(top,height/2,a));this.triangle([0,-height/2,0],p(base,-height/2,a),p(base,-height/2,b));}}}
export class QuadraticBezierCurve3{constructor(public a:Vector3,public b:Vector3,public c:Vector3){}point(t:number){return ['x','y','z'].map(k=>{const key=k as 'x';return (1-t)**2*this.a[key]+2*t*(1-t)*this.b[key]+t*t*this.c[key];});}}
export class TubeGeometry extends BufferGeometry{constructor(curve:QuadraticBezierCurve3,steps:number,r:number,sides:number,_closed=false){super();for(let i=0;i<steps;i++)for(let j=0;j<sides;j++){const p=(t:number,a:number)=>{const v=curve.point(t);return[v[0]+Math.cos(a)*r,v[1]+Math.sin(a)*r,v[2]];};const a=j*Math.PI*2/sides,b=(j+1)*Math.PI*2/sides;this.triangle(p(i/steps,a),p((i+1)/steps,a),p((i+1)/steps,b));this.triangle(p(i/steps,a),p((i+1)/steps,b),p(i/steps,b));}}}
export class Group{position=new Vector3();rotation=new Vector3();scale=new Vector3(1,1,1);poseTime=0;rig:CharacterRig|undefined;children:Group[]=[];add(o:Group){this.children.push(o);}remove(o:Group){this.children=this.children.filter(c=>c!==o);}traverse(fn:(o:any)=>void){fn(this);this.children.forEach(c=>c.traverse(fn));}}
export class Mesh extends Group{castShadow=false;receiveShadow=false;faceOverlay=false;rigPart=0;name="";constructor(public geometry:BufferGeometry,public material:Material){super();}}
export class Scene extends Group{}
export class PerspectiveCamera extends Group{focal=4.15;target=new Vector3(0,1.759,0);constructor(){super();this.position.set(0,1.759,7.4);}lookAt(x:number,y:number,z:number){this.target.set(x,y,z);}}
function rotate(v:number[],r:Vector3){let[x,y,z]=v;let c=Math.cos(r.x),s=Math.sin(r.x);[y,z]=[y*c-z*s,y*s+z*c];c=Math.cos(r.z),s=Math.sin(r.z);[x,y]=[x*c-y*s,x*s+y*c];c=Math.cos(r.y);s=Math.sin(r.y);[x,z]=[x*c+z*s,-x*s+z*c];return[x,y,z];}
export function collect(scene:Group,hideFaceOverlays=false){const triangles:any[]=[];function walk(o:Group,parents:Group[]){if(o instanceof Mesh&&!(hideFaceOverlays&&o.faceOverlay)){const g=o.geometry;for(let i=0;i<g.vertices.length;i+=9){const points=[];for(let j=0;j<3;j++){let p=g.vertices.slice(i+j*3,i+j*3+3);for(const t of [o,...parents]){p=p.map((v,k)=>v*[t.scale.x,t.scale.y,t.scale.z][k]);p=rotate(p,t.rotation);p=p.map((v,k)=>v+[t.position.x,t.position.y,t.position.z][k]);}points.push(p);}const a=points[0],b=points[1],c=points[2];const u=b.map((v:number,k:number)=>v-a[k]),v=c.map((n:number,k:number)=>n-a[k]);let n=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]],l=Math.hypot(...n)||1;n=n.map(x=>x/l);const normals=[];for(let j=0;j<3;j++){let normal=g.normals.slice(i+j*3,i+j*3+3);for(const t of [o,...parents]){normal=normal.map((v,k)=>v/[t.scale.x,t.scale.y,t.scale.z][k]);normal=rotate(normal,t.rotation);}const length=Math.hypot(...normal)||1;normals.push(normal.map(v=>v/length));}triangles.push({points,n,normals,color:o.material.color,colors:g.colors.slice(i/3,i/3+3),uvs:g.uvs.slice(i/3*2,(i/3+3)*2),faceCard:g.faceCard,roughness:o.material.roughness,rigPart:o.rigPart});}}o.children.forEach(c=>walk(c,[o,...parents]));}walk(scene,[]);return triangles;}

// Bind-space skeleton. Bone matrices are recomputed per frame, never cached with geometry.
type Matrix=number[];
const identity=():Matrix=>[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1];
function multiply(a:Matrix,b:Matrix){const c=new Array(16).fill(0);for(let col=0;col<4;col++)for(let row=0;row<4;row++)for(let k=0;k<4;k++)c[col*4+row]+=a[k*4+row]*b[col*4+k];return c;}
function pivotMatrix(p:Vector3,r:Vector3){const m=identity();for(let k=0;k<3;k++){const v=[0,0,0];v[k]=1;const q=rotate(v,r);for(let j=0;j<3;j++)m[k*4+j]=q[j];}const q=rotate([p.x,p.y,p.z],r);m[12]=p.x-q[0];m[13]=p.y-q[1];m[14]=p.z-q[2];return m;}
export class Bone{rotation=new Vector3();constructor(public name:string,public pivot:Vector3,public parent=-1){} }
export class CharacterRig{
 bones=[new Bone('spine',new Vector3(0,1.47,0)),new Bone('head',new Vector3(0,2.40,0),0),new Bone('leftShoulder',new Vector3(-.33,2.23,0),0),new Bone('leftElbow',new Vector3(-.46,1.84,.13),2),new Bone('rightShoulder',new Vector3(.33,2.23,0),0),new Bone('rightElbow',new Vector3(.46,1.84,.13),4),new Bone('ground',new Vector3())];
 palette(time:number){const wave=Math.sin(time*.9),breath=Math.sin(time*1.6);this.bones[0].rotation.set(breath*.008,0,wave*.009);this.bones[1].rotation.set(breath*.012,wave*.045,wave*.015);for(const [shoulder,elbow,side]of [[2,3,-1],[4,5,1]]){this.bones[shoulder].rotation.set(breath*.013,0,side*wave*.018);this.bones[elbow].rotation.set(breath*.045,0,side*breath*.020);}const matrices:Matrix[]=[];for(const b of this.bones){const local=pivotMatrix(b.pivot,b.rotation);matrices.push(b.parent<0?local:multiply(matrices[b.parent],local));}return matrices;}
}
function transform(m:Matrix,p:number[],normal=false){return [0,1,2].map(row=>m[row]*p[0]+m[4+row]*p[1]+m[8+row]*p[2]+(normal?0:m[12+row]));}
export function poseVertex(p:number[],n:number[],part:number,time:number){const matrices=new CharacterRig().palette(time);let bone=6,next=6,w=0;if(part===1)bone=next=1;if(part===2)bone=next=0;if(part===3||part===4){bone=part===3?2:4;next=bone+1;const f=Math.max(0,Math.min(1,(1.94-p[1])/.22));w=f*f*(3-2*f);}const a=transform(matrices[bone],p),b=transform(matrices[next],p),na=transform(matrices[bone],n,true),nb=transform(matrices[next],n,true);return {p:a.map((v,k)=>v*(1-w)+b[k]*w),n:na.map((v,k)=>v*(1-w)+nb[k]*w)};}
const vertexShader=`
attribute vec3 p;attribute vec3 c;attribute vec3 n;attribute float r;attribute float part;
uniform float angle;uniform float aspect;uniform vec3 cameraView;uniform mat4 bones[7];
varying vec3 color;varying vec3 normal;varying vec3 world;varying float roughness;
void main(){mat4 skin=bones[6];
 if(part>.5&&part<1.5)skin=bones[1];else if(part>1.5&&part<2.5)skin=bones[0];
 else if(part>2.5&&part<3.5)skin=bones[2]*smoothstep(1.72,1.94,p.y)+bones[3]*(1.-smoothstep(1.72,1.94,p.y));
 else if(part>3.5&&part<4.5)skin=bones[4]*smoothstep(1.72,1.94,p.y)+bones[5]*(1.-smoothstep(1.72,1.94,p.y));
 vec3 q=(skin*vec4(p,1.)).xyz;vec3 nn=mat3(skin)*n;
 mat3 turn=mat3(cos(angle),0.,-sin(angle),0.,1.,0.,sin(angle),0.,cos(angle));q=turn*q;normal=turn*nn;world=q;roughness=r;color=c;float d=cameraView.z-q.z;gl_Position=vec4(q.x*cameraView.x/aspect,(q.y-cameraView.y)*cameraView.x,(.4-q.z*.04)*d,d);
}`;
// Dielectric Cook-Torrance BRDF: GGX NDF, Schlick Fresnel and Smith visibility.
// Studio key/fill radiance and hemisphere ambient; no baked skin, hair or lighting.
const fragmentShader=`precision highp float;
varying vec3 color;varying vec3 normal;varying vec3 world;varying float roughness;
const float PI=3.14159265;
vec3 lightBRDF(vec3 n,vec3 v,vec3 l,vec3 base,float rough,vec3 radiance){
 vec3 h=normalize(v+l);float nv=max(dot(n,v),.001),nl=max(dot(n,l),0.),nh=max(dot(n,h),0.),vh=max(dot(v,h),0.);
 float a=rough*rough,a2=a*a,den=nh*nh*(a2-1.)+1.;float D=a2/(PI*den*den);float k=(rough+1.)*(rough+1.)/8.;float G=nv/(nv*(1.-k)+k)*nl/(nl*(1.-k)+k);
 vec3 F=vec3(.04)+(vec3(1.)-vec3(.04))*pow(1.-vh,5.);vec3 spec=D*G*F/max(.004,4.*nv*max(nl,.001));
 return ((vec3(1.)-F)*base/PI+spec)*radiance*nl;
}
void main(){vec3 n=normalize(normal),v=normalize(vec3(0.,1.75,7.4)-world),base=pow(color,vec3(2.2));float rough=clamp(roughness,.25,.95);
 vec3 linear=base*mix(vec3(.22,.235,.26),vec3(.34,.365,.41),n.y*.5+.5);
 linear+=lightBRDF(n,v,normalize(vec3(-.45,.7,1.)),base,rough,vec3(1.65,1.55,1.45));
 linear+=lightBRDF(n,v,normalize(vec3(.8,.25,.55)),base,rough,vec3(.46,.53,.64));
 linear+=lightBRDF(n,v,normalize(vec3(.2,.5,-1.)),base,rough,vec3(.35,.47,.55));
 gl_FragColor=vec4(pow(max(vec3(0.),linear),vec3(1./2.2)),1.);
}`;
export class WebGLRenderer{
 domElement:HTMLCanvasElement;private gl:WebGLRenderingContext|null=null;private ctx:CanvasRenderingContext2D|null=null;private program:WebGLProgram|null=null;private buffer:WebGLBuffer|null=null;private cachedModel:Group|null=null;private cachedCount=0;private ratio=1;ready=Promise.resolve(true);hasAtlas=false;outputColorSpace=0;toneMapping=0;toneMappingExposure=1;
 constructor(options:any){this.domElement=options.canvas||document.createElement('canvas');try{this.gl=this.domElement.getContext('webgl',{alpha:true,antialias:true,preserveDrawingBuffer:true});}catch{}if(!this.gl){this.ctx=this.domElement.getContext('2d');if(!this.ctx)throw Error('Canvas unavailable');return;}
 const gl=this.gl,shader=(type:number,source:string)=>{const s=gl.createShader(type)!;gl.shaderSource(s,source);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw Error(gl.getShaderInfoLog(s)||'Shader compilation failed');return s;};this.program=gl.createProgram()!;gl.attachShader(this.program,shader(gl.VERTEX_SHADER,vertexShader));gl.attachShader(this.program,shader(gl.FRAGMENT_SHADER,gl.getShaderPrecisionFormat(gl.FRAGMENT_SHADER,gl.HIGH_FLOAT)?.precision?fragmentShader:fragmentShader.replace("precision highp float","precision mediump float")));gl.linkProgram(this.program);if(!gl.getProgramParameter(this.program,gl.LINK_STATUS))throw Error(gl.getProgramInfoLog(this.program)||'Shader link failed');}
 get isSoftware(){return !this.gl;}get isContextLost(){return !!this.gl?.isContextLost();}
 setPixelRatio(r:number){this.ratio=r;}setSize(w:number,h:number,_style:boolean){this.domElement.width=Math.round(w*this.ratio);this.domElement.height=Math.round(h*this.ratio);}
 render(scene:Group,camera:PerspectiveCamera){if(this.isContextLost)throw Error('WebGL context lost');const model=scene.children[0]||scene;
 if(this.gl){const gl=this.gl;gl.viewport(0,0,this.domElement.width,this.domElement.height);gl.clearColor(0,0,0,0);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);gl.enable(gl.DEPTH_TEST);gl.depthFunc(gl.LEQUAL);gl.useProgram(this.program);
 if(this.cachedModel!==model){const angle=model.rotation.y;model.rotation.y=0;const tris=collect(scene);model.rotation.y=angle;const data:number[]=[];for(const t of tris)for(let i=0;i<3;i++){const hex=(t.colors[i]||t.color).replace('#','');const color=[0,2,4].map(k=>parseInt(hex.slice(k,k+2),16)/255);data.push(...t.points[i],...color,...t.normals[i],t.roughness,t.rigPart);}this.buffer ||=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,this.buffer);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(data),gl.STATIC_DRAW);this.cachedModel=model;this.cachedCount=data.length/11;}
 gl.bindBuffer(gl.ARRAY_BUFFER,this.buffer);for(const [name,offset]of [['p',0],['c',12],['n',24],['r',36],['part',40]] as const){const loc=gl.getAttribLocation(this.program!,name);if(loc<0)continue;gl.enableVertexAttribArray(loc);gl.vertexAttribPointer(loc,name==='r'||name==='part'?1:3,gl.FLOAT,false,44,offset);}gl.uniform1f(gl.getUniformLocation(this.program!,'angle'),model.rotation.y);const palette=(model.rig ||=new CharacterRig()).palette(model.poseTime);gl.uniformMatrix4fv(gl.getUniformLocation(this.program!,'bones[0]'),false,new Float32Array(palette.flat()));gl.uniform1f(gl.getUniformLocation(this.program!,'aspect'),this.domElement.width/Math.max(1,this.domElement.height));gl.uniform3f(gl.getUniformLocation(this.program!,'cameraView'),camera.focal,camera.target.y,camera.position.z);gl.drawArrays(gl.TRIANGLES,0,this.cachedCount);
 }else if(this.ctx){const ctx=this.ctx,w=this.domElement.width,h=this.domElement.height,tris=collect(scene);ctx.clearRect(0,0,w,h);tris.sort((a,b)=>a.points.reduce((s:number,p:number[])=>s+p[2],0)-b.points.reduce((s:number,p:number[])=>s+p[2],0));for(const t of tris){const n=[0,1,2].map(k=>t.normals.reduce((sum:number,v:number[])=>sum+v[k],0)/3),light=.70+.26*Math.max(0,n[0]*-.45+n[1]*.7+n[2]);const hex=t.color.replace('#','');ctx.fillStyle='rgb('+[0,2,4].map(k=>Math.min(255,Math.round(parseInt(hex.slice(k,k+2),16)*light))).join(',')+')';ctx.beginPath();t.points.forEach((p:number[],i:number)=>{const d=7.4-p[2],x=w/2+p[0]*4.15/(w/h)/d*w/2,y=h/2-(p[1]*4.15-7.3)/d*h/2;i?ctx.lineTo(x,y):ctx.moveTo(x,y);});ctx.closePath();ctx.fill();}}
 }
 dispose(){if(this.gl){this.gl.deleteBuffer(this.buffer);this.gl.deleteProgram(this.program);}}forceContextLoss(){this.gl?.getExtension('WEBGL_lose_context')?.loseContext();}
}
