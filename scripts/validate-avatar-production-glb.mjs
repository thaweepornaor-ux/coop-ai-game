// Read-only structural checks for exported avatar GLBs. No renderer or optimizer.
// Public API: validateAvatarGLB(Uint8Array | ArrayBuffer), runSelfTests().
const COMPONENTS = {
  5120: {size:1, get:"getInt8", signed:true, max:127},
  5121: {size:1, get:"getUint8", max:255},
  5122: {size:2, get:"getInt16", signed:true, max:32767},
  5123: {size:2, get:"getUint16", max:65535},
  5125: {size:4, get:"getUint32", max:4294967295},
  5126: {size:4, get:"getFloat32", floating:true}
};
const TYPE_SIZE = {SCALAR:1,VEC2:2,VEC3:3,VEC4:4,MAT2:4,MAT3:9,MAT4:16};
const isIndex = (v, length) => Number.isInteger(v) && v >= 0 && v < length;
const isNat = v => Number.isSafeInteger(v) && v >= 0;

function decodeUTF8(bytes) {
  let text = "";
  for (let i=0; i<bytes.length;) {
    const a = bytes[i++];
    if (a<128) { text += String.fromCharCode(a); continue; }
    let count, cp, minimum;
    if (a>=194 && a<=223) {count=1; cp=a&31; minimum=128;}
    else if (a>=224 && a<=239) {count=2; cp=a&15; minimum=2048;}
    else if (a>=240 && a<=244) {count=3; cp=a&7; minimum=65536;}
    else throw new Error("Invalid UTF-8 leading byte");
    for (let n=0;n<count;n++) {
      const b=bytes[i++];
      if (b===undefined || (b&192)!==128) throw new Error("Invalid UTF-8 continuation");
      cp=(cp<<6)|(b&63);
    }
    if (cp<minimum || cp>1114111 || (cp>=55296 && cp<=57343)) throw new Error("Invalid UTF-8 code point");
    text += String.fromCodePoint(cp);
  }
  return text;
}
function encodeUTF8(text) {
  const out=[];
  for (const ch of text) {
    const c=ch.codePointAt(0);
    if(c<128) out.push(c);
    else if(c<2048) out.push(192|(c>>6),128|(c&63));
    else if(c<65536) out.push(224|(c>>12),128|((c>>6)&63),128|(c&63));
    else out.push(240|(c>>18),128|((c>>12)&63),128|((c>>6)&63),128|(c&63));
  }
  return new Uint8Array(out);
}
function base64Bytes(text) {
  const s=text.replace(/\s/g,"");
  if (!/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(s)) throw new Error("Invalid base64");
  const alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
  const out=new Uint8Array(s.length/4*3-(s.endsWith("==")?2:s.endsWith("=")?1:0));
  let at=0;
  for(let i=0;i<s.length;i+=4) {
    const a=alphabet.indexOf(s[i]),b=alphabet.indexOf(s[i+1]);
    const c=s[i+2]==="="?0:alphabet.indexOf(s[i+2]),d=s[i+3]==="="?0:alphabet.indexOf(s[i+3]);
    const value=(a<<18)|(b<<12)|(c<<6)|d;
    if(at<out.length) out[at++]=(value>>16)&255;
    if(at<out.length) out[at++]=(value>>8)&255;
    if(at<out.length) out[at++]=value&255;
  }
  return out;
}
function layout(type, byteSize) {
  const n=TYPE_SIZE[type];
  if(!n) return null;
  if(type.startsWith("MAT")) {
    const d=Number(type.slice(3)), col=Math.ceil(d*byteSize/4)*4;
    return {n,size:d*col,offsets:Array.from({length:n},(_,i)=>Math.floor(i/d)*col+(i%d)*byteSize)};
  }
  return {n,size:n*byteSize,offsets:Array.from({length:n},(_,i)=>i*byteSize)};
}
function determinant4(v, at) {
  const m=Array.from({length:4},(_,row)=>Array.from({length:4},(_,col)=>v[at+col*4+row]));
  let det=1;
  for(let c=0;c<4;c++) {
    let p=c;
    for(let r=c+1;r<4;r++) if(Math.abs(m[r][c])>Math.abs(m[p][c])) p=r;
    if(m[p][c]===0) return 0;
    if(p!==c) {const tmp=m[p];m[p]=m[c];m[c]=tmp;det=-det;}
    const pivot=m[c][c];det*=pivot;
    for(let r=c+1;r<4;r++) {
      const k=m[r][c]/pivot;
      for(let j=c+1;j<4;j++) m[r][j]-=k*m[c][j];
    }
  }
  return det;
}

export function validateAvatarGLB(input, options={}) {
  const weightTolerance=options.weightTolerance ?? 0.001;
  const changeTolerance=options.changeTolerance ?? 0.000001;
  const quaternionTolerance=options.quaternionTolerance ?? 0.001;
  const maxValues=options.maxDecodedValues ?? 20000000;
  const maxIssues=options.maxIssues ?? 100;
  const report={
    ok:false,byteLength:0,errors:[],warnings:[],errorCount:0,warningCount:0,
    accessors:[],skins:[],animations:[],
    requiredClips:["idle","wave","celebrate"],
    limitations:[
      "Structural validation does not prove rendered shape, material appearance, garment coverage, or browser/mobile behavior.",
      "Four-weight normalization does not measure influence loss against the original Blender rig.",
      "Changed non-root channels do not prove that a named clip performs the intended idle, wave, or celebration.",
      "External buffer files are not read; required unavailable buffers make validation fail.",
      "Changing channels can cancel across a hierarchy or morph targets; rendered deformation is not proven.",
      "This helper is not a complete Khronos glTF validator."
    ]
  };
  const seenIssues=new Set();
  function issue(kind,code,where,message,details) {
    const key=kind+"|"+code+"|"+where;
    if(seenIssues.has(key)) return;
    seenIssues.add(key);
    report[kind==="errors"?"errorCount":"warningCount"]++;
    if(report[kind].length<maxIssues) report[kind].push({code,where,message,...(details===undefined?{}:{details})});
  }
  const error=(c,w,m,d)=>issue("errors",c,w,m,d);
  const warn=(c,w,m,d)=>issue("warnings",c,w,m,d);
  const finish=()=>{report.ok=report.errorCount===0;report.issuesTruncated=report.errorCount>report.errors.length||report.warningCount>report.warnings.length;return report;};
  if(!(input instanceof Uint8Array) && !(input instanceof ArrayBuffer)) {
    error("INPUT_TYPE","file","Expected Uint8Array or ArrayBuffer");return finish();
  }
  const bytes=input instanceof Uint8Array?input:new Uint8Array(input);
  report.byteLength=bytes.byteLength;
  if(bytes.length<12) {error("HEADER_TRUNCATED","file","GLB header is incomplete");return finish();}
  const dv=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength);
  if(dv.getUint32(0,true)!==0x46546c67) error("HEADER_MAGIC","file","Not a GLB file");
  if(dv.getUint32(4,true)!==2) error("HEADER_VERSION","file","Expected GLB version 2");
  if(dv.getUint32(8,true)!==bytes.length) error("HEADER_LENGTH","file","Header length differs from actual bytes",{declared:dv.getUint32(8,true),actual:bytes.length});
  if(report.errorCount) return finish();
  const chunks=[];
  let offset=12;
  while(offset<bytes.length) {
    if(offset+8>bytes.length) {error("CHUNK_HEADER","file","Truncated chunk header");break;}
    const length=dv.getUint32(offset,true),type=dv.getUint32(offset+4,true);
    if(length%4!==0) error("CHUNK_ALIGNMENT","chunks["+chunks.length+"]","Chunk length must be a multiple of 4");
    if(offset+8+length>bytes.length) {error("CHUNK_BOUNDS","file","Chunk extends beyond file");break;}
    chunks.push({type,data:bytes.subarray(offset+8,offset+8+length)});
    offset+=8+length;
  }
  if(report.errorCount) return finish();
  const jsonChunks=chunks.filter(c=>c.type===0x4e4f534a),binChunks=chunks.filter(c=>c.type===0x004e4942);
  if(chunks[0]?.type!==0x4e4f534a || jsonChunks.length!==1) {
    error("JSON_CHUNK","file","Exactly one JSON chunk must be first");return finish();
  }
  if(binChunks.length>1) error("BIN_CHUNKS","file","More than one BIN chunk");
  if(binChunks.length===1 && chunks[1]?.type!==0x004e4942) error("BIN_ORDER","file","BIN chunk must be second");
  for(let i=0;i<chunks.length;i++) if(![0x4e4f534a,0x004e4942].includes(chunks[i].type)) warn("UNKNOWN_CHUNK","chunks["+i+"]","Unknown chunk ignored");
  let gltf;
  try {gltf=JSON.parse(decodeUTF8(jsonChunks[0].data));}
  catch(e) {error("JSON_PARSE","file",String(e.message));return finish();}
  if(!gltf || typeof gltf!=="object" || Array.isArray(gltf) || gltf.asset?.version!=="2.0") {
    error("GLTF_VERSION","asset","Expected a glTF 2.0 object");return finish();
  }
  const arrays={};
  for(const key of ["buffers","bufferViews","accessors","nodes","meshes","skins","animations","scenes"]) {
    if(gltf[key]!==undefined && !Array.isArray(gltf[key])) error("ARRAY_TYPE",key,"Expected an array");
    arrays[key]=Array.isArray(gltf[key])?gltf[key]:[];
    for(let i=0;i<arrays[key].length;i++) if(!arrays[key][i] || typeof arrays[key][i]!=="object" || Array.isArray(arrays[key][i])) {
      error("OBJECT_TYPE",key+"["+i+"]","Expected an object");
      arrays[key][i]={};
    }
  }
  const buffers=arrays.buffers.map((b,i)=>{
    if(!isNat(b.byteLength)) {error("BUFFER_LENGTH","buffers["+i+"]","Invalid byteLength");return null;}
    let data=null;
    if(b.uri===undefined) {
      if(i!==0 || !binChunks[0]) {error("BUFFER_MISSING","buffers["+i+"]","No embedded BIN data");return null;}
      data=binChunks[0].data;
      if(data.length-b.byteLength>3) error("BIN_PADDING","buffers["+i+"]","BIN has more than 3 padding bytes");
    } else if(typeof b.uri==="string" && /^data:[^,]*;base64,/.test(b.uri)) {
      try {data=base64Bytes(b.uri.slice(b.uri.indexOf(",")+1));}
      catch(e) {error("BUFFER_DATA_URI","buffers["+i+"]",e.message);return null;}
    } else {error("EXTERNAL_BUFFER","buffers["+i+"]","External or unsupported URI buffer cannot be verified");return null;}
    if(b.byteLength>data.length) {error("BUFFER_BOUNDS","buffers["+i+"]","Declared buffer exceeds available bytes");return null;}
    return data.subarray(0,b.byteLength);
  });
  const views=arrays.bufferViews.map((v,i)=>{
    const where="bufferViews["+i+"]";
    if(!isIndex(v.buffer,buffers.length)||!buffers[v.buffer]) {error("VIEW_BUFFER",where,"Unavailable buffer");return null;}
    const start=v.byteOffset??0,len=v.byteLength;
    if(!isNat(start)||!isNat(len)||len===0||start+len>buffers[v.buffer].length) {error("VIEW_BOUNDS",where,"Invalid bufferView range");return null;}
    if(v.byteStride!==undefined && (!Number.isInteger(v.byteStride)||v.byteStride<4||v.byteStride>252||v.byteStride%4!==0||v.byteStride>len)) {
      error("VIEW_STRIDE",where,"byteStride must be a multiple of 4 between 4 and 252 and not exceed byteLength");return null;
    }
    if(v.target!==undefined && ![34962,34963].includes(v.target)) error("VIEW_TARGET",where,"Invalid bufferView target");
    return {data:buffers[v.buffer].subarray(start,start+len),offset:start,stride:v.byteStride};
  });
  const cache=new Map();
  let decodedValues=0;
  function accessor(index) {
    if(!isIndex(index,arrays.accessors.length)) {error("ACCESSOR_REFERENCE","accessors["+index+"]","Invalid accessor index");return null;}
    if(cache.has(index)) return cache.get(index);
    cache.set(index,null);
    const a=arrays.accessors[index],where="accessors["+index+"]",c=COMPONENTS[a.componentType],shape=c?layout(a.type,c.size):null;
    if(!c||!shape||!Number.isSafeInteger(a.count)||a.count<1) {error("ACCESSOR_FORMAT",where,"Invalid componentType, type, or count");return null;}
    if(a.normalized!==undefined && typeof a.normalized!=="boolean") error("ACCESSOR_NORMALIZED",where,"normalized must be boolean");
    if(a.normalized && ![5120,5121,5122,5123].includes(a.componentType)) error("ACCESSOR_NORMALIZED",where,"This componentType cannot be normalized");
    const countValues=a.count*shape.n;
    if(!Number.isSafeInteger(countValues)||decodedValues+countValues>maxValues) {error("DECODE_LIMIT",where,"Decoded-value budget exceeded",{maxValues});return null;}
    const values=new Float64Array(countValues);decodedValues+=countValues;
    function readRaw(viewIndex,start,count,outStart,itemShape,component,strideAllowed) {
      const view=views[viewIndex];
      if(!isIndex(viewIndex,views.length)||!view) {error("ACCESSOR_VIEW",where,"Invalid or unavailable bufferView");return false;}
      if(!isNat(start)||start%component.size!==0||view.offset%component.size!==0) {error("ACCESSOR_OFFSET",where,"Invalid component alignment");return false;}
      const stride=strideAllowed?(view.stride??itemShape.size):itemShape.size;
      if(!strideAllowed && view.stride!==undefined) {error("SPARSE_STRIDE",where,"Sparse bufferViews must be tightly packed");return false;}
      if(stride<itemShape.size||stride%component.size!==0) {error("ACCESSOR_STRIDE",where,"Stride is smaller than one element or misaligned");return false;}
      if(a.type.startsWith("MAT") && (view.offset%4!==0||start%4!==0)) {error("MATRIX_ALIGNMENT",where,"Matrix columns require 4-byte alignment");return false;}
      const required=start+(count-1)*stride+itemShape.size;
      if(required>view.data.length) {error("ACCESSOR_BOUNDS",where,"Accessor exceeds bufferView",{required,available:view.data.length});return false;}
      const data=new DataView(view.data.buffer,view.data.byteOffset,view.data.byteLength);
      for(let row=0;row<count;row++) for(let k=0;k<itemShape.n;k++) values[outStart+row*itemShape.n+k]=data[component.get](start+row*stride+itemShape.offsets[k],true);
      return true;
    }
    if(a.bufferView!==undefined && !readRaw(a.bufferView,a.byteOffset??0,a.count,0,shape,c,true)) return null;
    if(a.bufferView===undefined && (a.byteOffset??0)!==0) error("ACCESSOR_OFFSET",where,"byteOffset requires bufferView");
    if(a.sparse!==undefined) {
      const s=a.sparse;
      if(!s||!Number.isInteger(s.count)||s.count<1||s.count>a.count||!s.indices||!s.values||![5121,5123,5125].includes(s.indices.componentType)) {
        error("SPARSE_FORMAT",where,"Invalid sparse accessor");return null;
      }
      const iv=views[s.indices.bufferView],vv=views[s.values.bufferView],ic=COMPONENTS[s.indices.componentType];
      const io=s.indices.byteOffset??0,vo=s.values.byteOffset??0;
      if(!iv||!vv||iv.stride!==undefined||vv.stride!==undefined||!isNat(io)||!isNat(vo)||io%ic.size!==0||iv.offset%ic.size!==0||vo%c.size!==0||vv.offset%c.size!==0||io+s.count*ic.size>iv.data.length||vo+s.count*shape.size>vv.data.length) {
        error("SPARSE_BOUNDS",where,"Sparse indices/values are outside or misaligned to their views");return null;
      }
      if(a.type.startsWith("MAT")&&(vv.offset%4!==0||vo%4!==0)) error("SPARSE_MATRIX_ALIGNMENT",where,"Sparse matrix values are misaligned");
      const id=new DataView(iv.data.buffer,iv.data.byteOffset,iv.data.byteLength),vd=new DataView(vv.data.buffer,vv.data.byteOffset,vv.data.byteLength);
      let previous=-1;
      for(let j=0;j<s.count;j++) {
        const dest=id[ic.get](io+j*ic.size,true);
        if(dest<=previous||dest>=a.count) {error("SPARSE_INDEX",where,"Sparse indices must increase and be in bounds");return null;}
        previous=dest;
        for(let k=0;k<shape.n;k++) values[dest*shape.n+k]=vd[c.get](vo+j*shape.size+shape.offsets[k],true);
      }
    }
    if(a.normalized) for(let i=0;i<values.length;i++) values[i]=c.signed?Math.max(values[i]/c.max,-1):values[i]/c.max;
    let nonFinite=0;
    for(const v of values) if(!Number.isFinite(v)) nonFinite++;
    if(nonFinite) error("ACCESSOR_NONFINITE",where,"Decoded values contain NaN or Infinity",{count:nonFinite});
    for(const bound of ["min","max"]) if(a[bound]!==undefined && (!Array.isArray(a[bound])||a[bound].length!==shape.n||a[bound].some(v=>!Number.isFinite(v)))) error("ACCESSOR_MINMAX",where,"Invalid "+bound);
    if(Array.isArray(a.min)&&Array.isArray(a.max)&&a.min.length===shape.n&&a.max.length===shape.n) for(let k=0;k<shape.n;k++) {
      if(a.min[k]>a.max[k]) error("ACCESSOR_MINMAX_ORDER",where,"min exceeds max");
    }
    const decoded={index,type:a.type,count:a.count,componentType:a.componentType,normalized:!!a.normalized,components:shape.n,values,finite:nonFinite===0};
    report.accessors.push({index,type:a.type,count:a.count,componentType:a.componentType,normalized:!!a.normalized,finite:decoded.finite});
    cache.set(index,decoded);return decoded;
  }
  for(let i=0;i<arrays.accessors.length;i++) accessor(i);
  function tightlyPacked(index,where,usage) {
    const a=arrays.accessors[index],view=a&&views[a.bufferView];
    if(view?.stride!==undefined) error("NON_VERTEX_STRIDE",where,usage+" bufferViews must not define byteStride");
  }
  function vertexAligned(index,where) {
    const a=arrays.accessors[index],decoded=accessor(index),view=a&&views[a.bufferView];
    if(!a||!decoded||!view) return;
    const shape=layout(a.type,COMPONENTS[a.componentType].size),stride=view.stride??shape.size;
    if((a.byteOffset??0)%4!==0||(a.count>1&&stride%4!==0)) error("VERTEX_ALIGNMENT",where,"Vertex attribute elements must be 4-byte aligned inside the bufferView");
  }
  const nodes=arrays.nodes,parents=new Array(nodes.length).fill(-1);
  for(let i=0;i<nodes.length;i++) {
    const n=nodes[i],where="nodes["+i+"]";
    for(const [key,length] of [["matrix",16],["translation",3],["rotation",4],["scale",3]]) if(n[key]!==undefined && (!Array.isArray(n[key])||n[key].length!==length||n[key].some(v=>!Number.isFinite(v)))) error("NODE_TRANSFORM",where,"Invalid "+key);
    if(n.matrix!==undefined && ["translation","rotation","scale"].some(k=>n[k]!==undefined)) error("NODE_MATRIX_TRS",where,"Node mixes matrix and TRS");
    if(n.children!==undefined&&!Array.isArray(n.children)) error("NODE_CHILDREN",where,"children must be an array");
    for(const child of Array.isArray(n.children)?n.children:[]) {
      if(!isIndex(child,nodes.length)||child===i) {error("NODE_CHILD",where,"Invalid child");continue;}
      if(parents[child]!==-1) error("NODE_MULTIPARENT","nodes["+child+"]","Node has multiple parents");
      else parents[child]=i;
    }
    if(n.mesh!==undefined&&!isIndex(n.mesh,arrays.meshes.length)) error("NODE_MESH",where,"Invalid mesh");
    if(n.skin!==undefined&&!isIndex(n.skin,arrays.skins.length)) error("NODE_SKIN",where,"Invalid skin");
    if(n.skin!==undefined&&n.mesh===undefined) error("NODE_SKIN_MESH",where,"Skin requires a mesh");
  }
  for(let i=0;i<nodes.length;i++) {
    const visited=new Set();let at=i;
    while(at!==-1) {if(visited.has(at)) {error("NODE_CYCLE","nodes["+i+"]","Node hierarchy has a cycle");break;}visited.add(at);at=parents[at];}
  }
  const jointNodes=new Set(),deformNodes=new Set(),rootLike=new Set(),activeNodes=new Set();
  for(const scene of arrays.scenes) for(const n of Array.isArray(scene.nodes)?scene.nodes:[]) {
    if(isIndex(n,nodes.length)) rootLike.add(n);else error("SCENE_NODE","scenes","Invalid scene root");
  }
  const activeScene=gltf.scene??0;
  if(!isIndex(activeScene,arrays.scenes.length)) error("ACTIVE_SCENE","scene","Avatar needs a valid active scene");
  else {
    const pending=[...(Array.isArray(arrays.scenes[activeScene].nodes)?arrays.scenes[activeScene].nodes:[])];
    while(pending.length) {
      const n=pending.pop();
      if(!isIndex(n,nodes.length)||activeNodes.has(n)) continue;
      activeNodes.add(n);
      for(const child of Array.isArray(nodes[n].children)?nodes[n].children:[]) pending.push(child);
    }
  }
  function isAncestor(ancestor,node) {
    let at=node,guard=0;
    while(isIndex(at,nodes.length)&&guard++<=nodes.length) {if(at===ancestor) return true;at=parents[at];}
    return false;
  }
  const skinStates=arrays.skins.map((s,i)=>{
    const where="skins["+i+"]",j=Array.isArray(s.joints)?s.joints:[];
    if(!j.length||j.some(n=>!isIndex(n,nodes.length))||new Set(j).size!==j.length) error("SKIN_JOINTS",where,"Joint list must be nonempty, unique, and valid");
    const set=new Set(j.filter(n=>isIndex(n,nodes.length))),anchors=new Set(),skinRootLike=new Set();
    for(const n of set) {
      jointNodes.add(n);let at=parents[n],guard=0,hasJointParent=false;
      while(isIndex(at,nodes.length)&&guard++<=nodes.length) {if(set.has(at)) hasJointParent=true;at=parents[at];}
      if(!hasJointParent) anchors.add(n);
    }
    if(s.skeleton!==undefined) {
      if(isIndex(s.skeleton,nodes.length)) {
        anchors.add(s.skeleton);
        if(!Array.from(set).every(n=>isAncestor(s.skeleton,n))) error("SKIN_SKELETON_ANCESTRY",where,"skeleton must be a common ancestor of every joint");
      } else error("SKIN_SKELETON",where,"Invalid skeleton node");
    }
    if(set.size) {
      let at=set.values().next().value,guard=0,common=false;
      while(isIndex(at,nodes.length)&&guard++<=nodes.length) {if(Array.from(set).every(n=>isAncestor(at,n))) {common=true;break;}at=parents[at];}
      if(!common) error("SKIN_COMMON_ROOT",where,"All joints must have a common ancestor");
    }
    // Ancestors of this skin's root are global wrappers for this skin only.
    // Another skin may use one of these nodes as a genuinely deforming joint.
    for(const anchor of anchors) {
      let at=anchor,guard=0;
      while(isIndex(at,nodes.length)&&guard++<=nodes.length) {skinRootLike.add(at);rootLike.add(at);at=parents[at];}
    }
    if(s.inverseBindMatrices!==undefined) {
      const ib=accessor(s.inverseBindMatrices);
      tightlyPacked(s.inverseBindMatrices,where,"Inverse bind matrix");
      if(!ib||ib.type!=="MAT4"||ib.componentType!==5126||ib.count<j.length) error("INVERSE_BIND_FORMAT",where,"Expected at least one float MAT4 inverse bind per joint");
      else if(ib.finite) for(let k=0;k<ib.count;k++) {
        const at=k*16;
        if(ib.values[at+3]!==0||ib.values[at+7]!==0||ib.values[at+11]!==0||ib.values[at+15]!==1)
          error("INVERSE_BIND_AFFINE",where,"Inverse bind bottom row must be [0, 0, 0, 1]",{paletteIndex:k});
        const det=determinant4(ib.values,at);
        if(det===0||!Number.isFinite(det)) {error("INVERSE_BIND_SINGULAR",where,"Inverse bind matrix is not invertible",{paletteIndex:k});break;}
      }
    }
    return {index:i,joints:j,used:new Set(),allUsed:new Set(),rootLike:skinRootLike,deformNodes:new Set(),meshNodes:[],verticesChecked:0,maximumWeightSumError:0};
  });
  for(let mi=0;mi<arrays.meshes.length;mi++) {
    const mesh=arrays.meshes[mi],where="meshes["+mi+"]";
    if(!Array.isArray(mesh.primitives)||!mesh.primitives.length) {error("MESH_PRIMITIVES",where,"Mesh has no primitives");continue;}
    for(let pi=0;pi<mesh.primitives.length;pi++) {
      const p=mesh.primitives[pi],pw=where+".primitives["+pi+"]",attrs=p?.attributes;
      if(!attrs||typeof attrs!=="object") {error("PRIMITIVE_ATTRIBUTES",pw,"Missing attributes");continue;}
      for(const [name,idx] of Object.entries(attrs)) {accessor(idx);vertexAligned(idx,pw+"."+name);}
      if(p.indices!==undefined) {
        const ix=accessor(p.indices),pos=accessor(attrs.POSITION);
        tightlyPacked(p.indices,pw,"Mesh index");
        if(!ix||ix.type!=="SCALAR"||![5121,5123,5125].includes(ix.componentType)||ix.normalized) error("MESH_INDEX_FORMAT",pw,"Invalid mesh index accessor");
        else if(pos) for(const value of ix.values) if(!isIndex(value,pos.count)) {error("MESH_INDEX_BOUNDS",pw,"Mesh indices exceed vertex count");break;}
      }
      for(const name of Object.keys(attrs)) if(/^(JOINTS|WEIGHTS)_[1-9][0-9]*$/.test(name)) error("EXTRA_SKIN_SET",pw+"."+name,"Production runtime supports only four JOINTS_0/WEIGHTS_0 influences");
      const pos=accessor(attrs.POSITION);
      if(!pos||pos.type!=="VEC3") error("POSITION_FORMAT",pw,"POSITION must be VEC3");
      if(pos) for(const [name,idx] of Object.entries(attrs)) {
        const a=accessor(idx);
        if(a && a.count!==pos.count) error("ATTRIBUTE_COUNT",pw+"."+name,"Attribute count differs from POSITION");
      }
      if(p.targets!==undefined && !Array.isArray(p.targets)) error("MORPH_TARGETS",pw,"targets must be an array");
      for(const [ti,target] of (Array.isArray(p.targets)?p.targets:[]).entries()) {
        if(!target||typeof target!=="object"||Array.isArray(target)) {error("MORPH_TARGET",pw+".targets["+ti+"]","Invalid morph target");continue;}
        for(const [name,idx] of Object.entries(target)) {
          const a=accessor(idx);vertexAligned(idx,pw+".targets["+ti+"]."+name);
          if(!["POSITION","NORMAL","TANGENT"].includes(name)||!a||a.type!=="VEC3"||pos&&a.count!==pos.count) error("MORPH_ACCESSOR",pw+".targets["+ti+"]."+name,"Invalid morph target accessor");
        }
      }
    }
  }
  for(let ni=0;ni<nodes.length;ni++) {
    const n=nodes[ni],state=skinStates[n.skin],mesh=arrays.meshes[n.mesh];
    if(!state||!mesh||!Array.isArray(mesh.primitives)) continue;
    state.meshNodes.push(ni);
    if(activeNodes.has(ni)&&state.joints.some(j=>!activeNodes.has(j))) error("SKIN_SCENE_REACHABILITY","nodes["+ni+"]","Every joint must be reachable in the active scene containing its skinned mesh");
    for(let pi=0;pi<mesh.primitives.length;pi++) {
      const attrs=mesh.primitives[pi]?.attributes??{},where="nodes["+ni+"].mesh.primitives["+pi+"]";
      const pos=accessor(attrs.POSITION),ji=accessor(attrs.JOINTS_0),we=accessor(attrs.WEIGHTS_0);
      if(!ji||!we||ji.type!=="VEC4"||we.type!=="VEC4"||![5121,5123].includes(ji.componentType)||ji.normalized||![5121,5123,5126].includes(we.componentType)||(we.componentType!==5126&&!we.normalized)||!pos||ji.count!==pos.count||we.count!==pos.count) {
        error("SKIN_ATTRIBUTE_FORMAT",where,"Expected matching VEC4 unsigned joint indices and float/normalized unsigned weights");continue;
      }
      let invalidIndices=0,invalidWeights=0,badSums=0,badQuantSums=0,duplicateJoints=0;const samples=[];
      const quantMax=we.componentType===5121?255:we.componentType===5123?65535:null;
      for(let v=0;v<ji.count;v++) {
        let sum=0,rawSum=0;const positiveJoints=new Set();
        for(let k=0;k<4;k++) {
          const ix=ji.values[v*4+k],w=we.values[v*4+k];
          if(!isIndex(ix,state.joints.length)) invalidIndices++;
          if(!Number.isFinite(w)||w<0||w>1) invalidWeights++;
          if(Number.isFinite(w)) {sum+=w;if(quantMax!==null) rawSum+=Math.round(w*quantMax);}
          if(w>0&&isIndex(ix,state.joints.length)) {
            if(positiveJoints.has(ix)) duplicateJoints++;positiveJoints.add(ix);
            state.used.add(ix);state.allUsed.add(ix);
          }
        }
        if(quantMax!==null&&rawSum!==quantMax) badQuantSums++;
        const delta=Math.abs(sum-1);state.maximumWeightSumError=Math.max(state.maximumWeightSumError,delta);
        if(delta>weightTolerance) {badSums++;if(samples.length<5)samples.push({vertex:v,sum});}
      }
      state.verticesChecked+=ji.count;
      if(invalidIndices) error("SKIN_INDEX_BOUNDS",where,"Joint indices must be integer palette indices in bounds",{count:invalidIndices});
      if(invalidWeights) error("SKIN_WEIGHT_RANGE",where,"Weights must be finite and nonnegative",{count:invalidWeights});
      if(badSums) error("SKIN_WEIGHT_SUM",where,"The four weights must sum to 1",{count:badSums,tolerance:weightTolerance,samples});
      if(badQuantSums) error("SKIN_QUANTIZED_WEIGHT_SUM",where,"Quantized raw weights must sum exactly to "+quantMax,{count:badQuantSums});
      if(duplicateJoints) error("SKIN_DUPLICATE_JOINT",where,"A joint must not have more than one positive weight for the same vertex",{count:duplicateJoints});
      for(const key of Object.keys(attrs).filter(k=>/^JOINTS_[1-9][0-9]*$/.test(k))) {
        const extraJ=accessor(attrs[key]),extraW=accessor(attrs[key.replace("JOINTS","WEIGHTS")]);
        if(!extraJ||!extraW||extraJ.components!==4||extraW.components!==4||extraJ.count!==ji.count||extraW.count!==ji.count) continue;
        for(let k=0;k<extraJ.values.length;k++) if(extraW.values[k]>0&&isIndex(extraJ.values[k],state.joints.length)) state.allUsed.add(extraJ.values[k]);
      }
    }
  }
  // Only nodes that can affect a positively weighted vertex count as deforming.
  deformNodes.clear();
  for(const state of skinStates) if(state.meshNodes.some(n=>activeNodes.has(n))) for(const paletteIndex of state.used) {
    let at=state.joints[paletteIndex],guard=0;
    while(isIndex(at,nodes.length)&&guard++<=nodes.length) {deformNodes.add(at);state.deformNodes.add(at);at=parents[at];}
  }
  if(!skinStates.some(s=>s.verticesChecked>0)) error("SKINNED_GEOMETRY_MISSING","skins","No verifiable skinned geometry");
  for(const state of skinStates) {
    if(!state.meshNodes.length) warn("UNUSED_SKIN","skins["+state.index+"]","Skin is not referenced by a mesh node");
    const supported=Array.from(state.used).sort((a,b)=>a-b),all=Array.from(state.allUsed).sort((a,b)=>a-b);
    const unused=state.joints.map((_,i)=>i).filter(i=>!state.allUsed.has(i));
    report.skins.push({
      index:state.index,jointCount:state.joints.length,usedJointCount:all.length,supportedFourWeightUsedJointCount:supported.length,
      unusedJointCount:unused.length,usedPaletteIndices:all,unusedPaletteIndices:unused,
      extraOnlyPaletteIndices:all.filter(i=>!state.used.has(i)),meshNodes:state.meshNodes,
      verticesChecked:state.verticesChecked,maximumWeightSumError:state.maximumWeightSumError,
      joints:state.joints.map((node,paletteIndex)=>({paletteIndex,node,name:nodes[node]?.name??null,used:state.allUsed.has(paletteIndex)}))
    });
  }
  if(!skinStates.length) error("SKINS_MISSING","skins","Avatar asset has no skin");
  if(!skinStates.some(s=>s.verticesChecked>0&&s.meshNodes.some(n=>activeNodes.has(n)))) error("ACTIVE_SKINNED_GEOMETRY","scene","Active scene has no verifiable skinned avatar");
  const clipNames=new Map();
  for(let ai=0;ai<arrays.animations.length;ai++) {
    const animation=arrays.animations[ai],where="animations["+ai+"]",name=typeof animation.name==="string"?animation.name:"";
    const normalized=name.trim().toLowerCase();
    if(clipNames.has(normalized)) error("CLIP_DUPLICATE",where,"Duplicate clip name");else clipNames.set(normalized,ai);
    const channels=Array.isArray(animation.channels)?animation.channels:[],samplers=Array.isArray(animation.samplers)?animation.samplers:[];
    if(!channels.length) error("ANIMATION_CHANNELS",where,"Animation has no channels");
    const details=[];let changedCount=0,deformingCount=0,duration=0;
    const targeted=new Set();
    for(let ci=0;ci<channels.length;ci++) {
      const ch=channels[ci],cw=where+".channels["+ci+"]",target=ch?.target??{},sampler=samplers[ch?.sampler];
      if(!isIndex(ch?.sampler,samplers.length)||!sampler||!isIndex(target.node,nodes.length)||!["translation","rotation","scale","weights"].includes(target.path)) {
        error("ANIMATION_REFERENCE",cw,"Invalid sampler, target node, or path");continue;
      }
      const targetKey=target.node+"/"+target.path;
      if(targeted.has(targetKey)) error("ANIMATION_DUPLICATE_TARGET",cw,"Multiple channels target the same node/path");targeted.add(targetKey);
      if(nodes[target.node].matrix!==undefined) error("ANIMATION_MATRIX_NODE",cw,"Animated TRS node uses a matrix");
      const times=accessor(sampler.input),out=accessor(sampler.output),interpolation=sampler.interpolation??"LINEAR";
      tightlyPacked(sampler.input,cw,"Animation input");tightlyPacked(sampler.output,cw,"Animation output");
      if(!times||!out||times.type!=="SCALAR"||times.componentType!==5126||times.normalized||out.componentType!==5126||out.normalized||!["LINEAR","STEP","CUBICSPLINE"].includes(interpolation)) {
        error("ANIMATION_ACCESSOR",cw,"Invalid animation accessor or interpolation");continue;
      }
      if(!times.finite||!out.finite) continue;
      let invalidTime=false;
      for(let t=0;t<times.count;t++) if(times.values[t]<0||(t>0&&times.values[t]<=times.values[t-1])) invalidTime=true;
      if(invalidTime) error("ANIMATION_TIME",cw,"Times must be finite, nonnegative, and strictly increasing");
      duration=Math.max(duration,times.values[times.count-1]-times.values[0]);
      let components=target.path==="rotation"?4:3,outputType=target.path==="rotation"?"VEC4":"VEC3";
      if(target.path==="weights") {
        const m=arrays.meshes[nodes[target.node].mesh];
        components=m?.primitives?.[0]?.targets?.length??0;outputType="SCALAR";
        if(!components||m.primitives.some(p=>(p?.targets?.length??0)!==components)) {error("ANIMATION_MORPH_TARGET",cw,"Cannot determine consistent morph target count");continue;}
      }
      const factor=interpolation==="CUBICSPLINE"?3:1;
      const expected=times.count*factor*(target.path==="weights"?components:1);
      if(out.type!==outputType||out.count!==expected) {error("ANIMATION_OUTPUT_COUNT",cw,"Output count/type does not match input/path",{expected,actual:out.count});continue;}
      const sample=t=>{
        const base=(t*factor+(factor===3?1:0))*components;
        return out.values.subarray(base,base+components);
      };
      const first=sample(0),firstNorm=target.path==="rotation"?Math.hypot(...first):1;
      const firstRotation=target.path==="rotation"&&firstNorm>0.000000000001?Array.from(first,v=>v/firstNorm):null;
      let changed=false;const changedComponents=new Set();
      for(let t=0;t<times.count;t++) {
        const current=sample(t);
        if(target.path==="rotation") {
          const norm=Math.hypot(...current);
          if(norm<=0.000000000001||Math.abs(norm-1)>quaternionTolerance) error("ANIMATION_QUATERNION",cw,"Rotation keys must be unit quaternions");
          if(!firstRotation||norm<=0.000000000001) continue;
          let same=0,opposite=0;
          for(let k=0;k<4;k++){same+=(current[k]/norm-firstRotation[k])**2;opposite+=(current[k]/norm+firstRotation[k])**2;}
          if(Math.min(same,opposite)>changeTolerance**2) changed=true;
        } else for(let k=0;k<components;k++) if(Math.abs(current[k]-first[k])>changeTolerance) {changed=true;changedComponents.add(k);}
      }
      // Evaluate interior cubic samples: equal keys may still move, while purely
      // radial quaternion tangents change length but not visible orientation.
      if(factor===3) for(let t=0;t<times.count-1;t++) {
        const dt=times.values[t+1]-times.values[t],a=sample(t),b=sample(t+1);
        for(const u of [0.25,0.5,0.75]) {
          const h00=2*u**3-3*u**2+1,h10=u**3-2*u**2+u,h01=-2*u**3+3*u**2,h11=u**3-u**2;
          const value=Array.from({length:components},(_,k)=>h00*a[k]+h10*dt*out.values[(t*3+2)*components+k]+h01*b[k]+h11*dt*out.values[((t+1)*3)*components+k]);
          if(target.path==="rotation") {
            const norm=Math.hypot(...value);
            if(norm<0.000000000001) {error("ANIMATION_QUATERNION_PATH",cw,"Cubic interpolation produces a zero quaternion");continue;}
            if(!firstRotation) continue;
            let same=0,opposite=0;
            for(let k=0;k<4;k++){same+=(value[k]/norm-firstRotation[k])**2;opposite+=(value[k]/norm+firstRotation[k])**2;}
            if(Math.min(same,opposite)>changeTolerance**2) changed=true;
          } else for(let k=0;k<components;k++) if(Math.abs(value[k]-first[k])>changeTolerance) {changed=true;changedComponents.add(k);}
        }
      }
      const nonRootDeform=skinStates.some(s=>s.deformNodes.has(target.node)&&!s.rootLike.has(target.node));
      const morphGeometryMotion=target.path==="weights"&&activeNodes.has(target.node)&&Array.from(changedComponents).some(ti=>
        arrays.meshes[nodes[target.node].mesh].primitives.some(p=>{
          const idx=p.targets?.[ti]?.POSITION;if(idx===undefined) return false;
          const delta=accessor(idx);return delta?.finite&&delta.values.some(v=>Math.abs(v)>changeTolerance);
        }));
      const isDeforming=changed&&(morphGeometryMotion||target.path!=="weights"&&nonRootDeform);
      if(changed) changedCount++;if(isDeforming) deformingCount++;
      details.push({node:target.node,nodeName:nodes[target.node].name??null,path:target.path,keys:times.count,interpolation,changed,
        isJoint:jointNodes.has(target.node),rootLike:rootLike.has(target.node)&&!nonRootDeform,deforming:isDeforming});
    }
    if(changedCount===0) error("CLIP_STATIC",where,"No channel values produce a changing pose");
    else if(deformingCount===0) error("CLIP_ROOT_ONLY",where,"Only global or geometry-inert channels change; no non-root deformation channel");
    report.animations.push({index:ai,name,duration,channelCount:channels.length,changedChannelCount:changedCount,deformingChannelCount:deformingCount,channels:details});
  }
  for(const name of report.requiredClips) if(!clipNames.has(name)) error("CLIP_MISSING","animations."+name,"Required clip is absent: "+name);
  report.decodedValueCount=decodedValues;
  return finish();
}

function fixtureGLB(change) {
  const data=[],views=[],accessors=[];
  function add(values,type,componentType) {
    while(data.length%4) data.push(0);
    const component=COMPONENTS[componentType],raw=new Uint8Array(values.length*component.size),dv=new DataView(raw.buffer);
    const setter={5120:"setInt8",5121:"setUint8",5122:"setInt16",5123:"setUint16",5125:"setUint32",5126:"setFloat32"}[componentType];
    values.forEach((v,i)=>dv[setter](i*component.size,v,true));
    const offset=data.length;data.push(...raw);
    const view=views.length;views.push({buffer:0,byteOffset:offset,byteLength:raw.length});
    const idx=accessors.length;accessors.push({bufferView:view,componentType,count:values.length/TYPE_SIZE[type],type});return idx;
  }
  const pos=add([0,0,0,0,1,0,1,0,0],"VEC3",5126),ji=add([0,1,0,0,1,0,0,0,0,1,0,0],"VEC4",5123);
  const we=add([0.5,0.5,0,0,1,0,0,0,0.5,0.5,0,0],"VEC4",5126);
  const identity=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1];
  const ib=add([...identity,...identity,...identity],"MAT4",5126);
  const time=add([0,1,2],"SCALAR",5126),move=add([0,0,0,0,0.2,0,0,0,0],"VEC3",5126);
  const json={
    asset:{version:"2.0"},buffers:[{byteLength:data.length}],bufferViews:views,accessors,
    scenes:[{nodes:[0]}],scene:0,
    nodes:[{name:"Scene",children:[1,3]},{name:"RootBone",children:[2,4]},{name:"Arm"},{mesh:0,skin:0},{name:"UnusedJoint",children:[]}],
    meshes:[{primitives:[{attributes:{POSITION:pos,JOINTS_0:ji,WEIGHTS_0:we}}]}],
    skins:[{skeleton:1,joints:[1,2,4],inverseBindMatrices:ib}],
    animations:["idle","wave","celebrate"].map(name=>({name,samplers:[{input:time,output:move}],channels:[{sampler:0,target:{node:2,path:"translation"}}]}))
  };
  if(change) change({json,data,add,indices:{pos,ji,we,ib,time,move}});
  json.buffers[0].byteLength=data.length;
  const text=encodeUTF8(JSON.stringify(json)),jsonLength=Math.ceil(text.length/4)*4,binLength=Math.ceil(data.length/4)*4;
  const result=new Uint8Array(12+8+jsonLength+8+binLength),header=new DataView(result.buffer);
  header.setUint32(0,0x46546c67,true);header.setUint32(4,2,true);header.setUint32(8,result.length,true);
  header.setUint32(12,jsonLength,true);header.setUint32(16,0x4e4f534a,true);
  result.fill(32,20,20+jsonLength);result.set(text,20);
  const bin=20+jsonLength;header.setUint32(bin,binLength,true);header.setUint32(bin+4,0x004e4942,true);result.set(data,bin+8);return result;
}
function patchFixtureScalar(f,accessorIndex,componentIndex,value) {
  const a=f.json.accessors[accessorIndex],v=f.json.bufferViews[a.bufferView],c=COMPONENTS[a.componentType];
  const raw=new Uint8Array(c.size),dv=new DataView(raw.buffer),setter={5123:"setUint16",5126:"setFloat32"}[a.componentType];
  dv[setter](0,value,true);
  for(let i=0;i<c.size;i++) f.data[v.byteOffset+componentIndex*c.size+i]=raw[i];
}
export function runSelfTests() {
  const results=[];
  function test(name,bytes,expectedCode,extraCheck) {
    const report=validateAvatarGLB(bytes);
    const ok=expectedCode?report.errors.some(e=>e.code===expectedCode):report.ok;
    const passed=ok&&(!extraCheck||extraCheck(report));
    results.push({name,passed,...(!passed?{errors:report.errors}:{} )});
  }
  test("valid rig, unused palette joint, three changing limb clips",fixtureGLB(),null,r=>r.skins[0].usedJointCount===2&&r.skins[0].unusedJointCount===1);
  test("truncated file",fixtureGLB().subarray(0,100),"HEADER_LENGTH");
  test("out-of-range joint",fixtureGLB(f=>patchFixtureScalar(f,f.indices.ji,0,99)),"SKIN_INDEX_BOUNDS");
  test("four weights not normalized",fixtureGLB(f=>patchFixtureScalar(f,f.indices.we,0,0.2)),"SKIN_WEIGHT_SUM");
  test("nonfinite weight",fixtureGLB(f=>patchFixtureScalar(f,f.indices.we,0,NaN)),"ACCESSOR_NONFINITE");
  test("extra influence sets",fixtureGLB(f=>{const a=f.json.meshes[0].primitives[0].attributes;a.JOINTS_1=f.indices.ji;a.WEIGHTS_1=f.indices.we;}),"EXTRA_SKIN_SET");
  test("root-only clips",fixtureGLB(f=>f.json.animations.forEach(a=>a.channels[0].target.node=0)),"CLIP_ROOT_ONLY");
  test("constant keys",fixtureGLB(f=>{for(let i=0;i<9;i++)patchFixtureScalar(f,f.indices.move,i,0);}),"CLIP_STATIC");
  test("missing required clip",fixtureGLB(f=>f.json.animations.pop()),"CLIP_MISSING");
  test("unordered animation time",fixtureGLB(f=>patchFixtureScalar(f,f.indices.time,2,0.5)),"ANIMATION_TIME");
  test("accessor outside bufferView",fixtureGLB(f=>f.json.accessors[f.indices.pos].count=1000),"ACCESSOR_BOUNDS");
  test("sparse changing animation keys",fixtureGLB(f=>{
    const out=f.json.accessors[f.indices.move];delete out.bufferView;
    const si=f.add([1],"SCALAR",5123),sv=f.add([0,0.2,0],"VEC3",5126);
    out.sparse={count:1,indices:{bufferView:f.json.accessors[si].bufferView,componentType:5123},values:{bufferView:f.json.accessors[sv].bufferView}};
  }),null);
  test("padded byte MAT3 accessor",fixtureGLB(f=>{
    while(f.data.length%4)f.data.push(0);const at=f.data.length;
    f.data.push(1,0,0,0,0,1,0,0,0,0,1,0);
    const view=f.json.bufferViews.length;f.json.bufferViews.push({buffer:0,byteOffset:at,byteLength:12});
    f.json.accessors.push({bufferView:view,componentType:5121,count:1,type:"MAT3"});
  }),null);
  test("quaternion sign flip is not motion",fixtureGLB(f=>{
    const q=f.add([0,0,0,1,0,0,0,-1,0,0,0,1],"VEC4",5126);
    f.json.animations.forEach(a=>{a.samplers[0].output=q;a.channels[0].target.path="rotation";});
  }),"CLIP_STATIC");
  test("unused joint motion cannot pass a clip",fixtureGLB(f=>f.json.animations.forEach(a=>a.channels[0].target.node=4)),"CLIP_ROOT_ONLY");
  test("unavailable external buffer",fixtureGLB(f=>f.json.buffers[0].uri="external.bin"),"EXTERNAL_BUFFER");
  test("cubic translation between equal endpoint keys",fixtureGLB(f=>{
    const time=f.add([0,1],"SCALAR",5126);
    const out=f.add([0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,0,0,0],"VEC3",5126);
    f.json.animations.forEach(a=>a.samplers[0]={input:time,output:out,interpolation:"CUBICSPLINE"});
  }),null);
  test("radial cubic quaternion tangents are not rotation",fixtureGLB(f=>{
    const time=f.add([0,1],"SCALAR",5126);
    const out=f.add([0,0,0,0,0,0,0,1,0,0,0,0.5,0,0,0,0,0,0,0,1,0,0,0,0],"VEC4",5126);
    f.json.animations.forEach(a=>{a.samplers[0]={input:time,output:out,interpolation:"CUBICSPLINE"};a.channels[0].target.path="rotation";});
  }),"CLIP_STATIC");
  test("invalid joint weights cannot be hidden by sparse data",fixtureGLB(f=>{
    const a=f.json.accessors[f.indices.we];delete a.bufferView;
    const idx=f.add([0,0],"SCALAR",5123),value=f.add([1,0,0,0,1,0,0,0],"VEC4",5126);
    a.sparse={count:2,indices:{bufferView:f.json.accessors[idx].bufferView,componentType:5123},values:{bufferView:f.json.accessors[value].bufferView}};
  }),"SPARSE_INDEX");
  test("Armature wrapper motion is global-only",fixtureGLB(f=>{
    f.json.nodes.push({name:"ArmatureWrapper",children:[1]});f.json.nodes[0].children=[5,3];
    f.json.animations.forEach(a=>a.channels[0].target.node=5);
  }),"CLIP_ROOT_ONLY");
  test("Armature wrapper without explicit skeleton is global-only",fixtureGLB(f=>{
    f.json.nodes.push({name:"ArmatureWrapper",children:[1]});f.json.nodes[0].children=[5,3];delete f.json.skins[0].skeleton;
    f.json.animations.forEach(a=>a.channels[0].target.node=5);
  }),"CLIP_ROOT_ONLY");
  test("root-like node for one skin still deforms another skin",fixtureGLB(f=>{
    const joint=f.add(Array(12).fill(0),"VEC4",5123),weights=f.add([1,0,0,0,1,0,0,0,1,0,0,0],"VEC4",5126);
    const ib=f.add([1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1],"MAT4",5126);
    f.json.meshes.push({primitives:[{attributes:{POSITION:f.indices.pos,JOINTS_0:joint,WEIGHTS_0:weights}}]});
    f.json.skins.push({skeleton:2,joints:[2],inverseBindMatrices:ib});
    f.json.nodes.push({name:"OtherSkinnedMesh",mesh:1,skin:1});f.json.nodes[0].children.push(5);
  }),null,r=>r.animations.every(a=>a.deformingChannelCount===1));
  test("quaternion length jitter is not orientation motion",fixtureGLB(f=>{
    const q=f.add([0,0,0,1,0,0,0,1.0005,0,0,0,1],"VEC4",5126);
    f.json.animations.forEach(a=>{a.samplers[0].output=q;a.channels[0].target.path="rotation";});
  }),"CLIP_STATIC");
  test("non-affine inverse bind matrix is rejected",fixtureGLB(f=>patchFixtureScalar(f,f.indices.ib,3,0.125)),"INVERSE_BIND_AFFINE");
  test("non-unit affine homogeneous component is rejected",fixtureGLB(f=>patchFixtureScalar(f,f.indices.ib,15,1.125)),"INVERSE_BIND_AFFINE");
  test("active mesh cannot use joints outside its scene",fixtureGLB(f=>f.json.scenes[0].nodes=[3]),"SKIN_SCENE_REACHABILITY");
  test("skeleton must be an ancestor of all skin joints",fixtureGLB(f=>f.json.skins[0].skeleton=4),"SKIN_SKELETON_ANCESTRY");
  test("skin joints must have a common ancestor",fixtureGLB(f=>f.json.nodes[1].children=[2]),"SKIN_COMMON_ROOT");
  function morphFixture(nonzero,secondTarget=false) {
    return fixtureGLB(f=>{
      const delta=f.add(nonzero?[0.1,0,0,0,0,0,0,0,0]:Array(9).fill(0),"VEC3",5126);
      f.json.meshes[0].primitives[0].targets=[{POSITION:delta}];
      if(secondTarget) f.json.meshes[0].primitives[0].targets.push({POSITION:f.add([0.1,0,0,0,0,0,0,0,0],"VEC3",5126)});
      const value=f.add(secondTarget?[0,0,1,0,0,0]:[0,1,0],"SCALAR",5126);
      f.json.animations.forEach(a=>{a.samplers[0].output=value;a.channels[0].target={node:3,path:"weights"};});
    });
  }
  test("zero position morph deltas cannot prove deformation",morphFixture(false),"CLIP_ROOT_ONLY");
  test("changing a nonzero position morph is accepted",morphFixture(true),null);
  test("changing only a zero morph target is not deformation",morphFixture(false,true),"CLIP_ROOT_ONLY");
  test("misaligned float offsets cannot compensate each other",fixtureGLB(f=>{
    const a=f.json.accessors[f.indices.we],v=f.json.bufferViews[a.bufferView];v.byteOffset-=2;v.byteLength+=2;a.byteOffset=2;
  }),"ACCESSOR_OFFSET");
  test("vertex-relative offset must be 4-byte aligned",fixtureGLB(f=>{
    const a=f.json.accessors[f.indices.ji],v=f.json.bufferViews[a.bufferView];v.byteOffset-=2;v.byteLength+=2;a.byteOffset=2;
  }),"VERTEX_ALIGNMENT");
  function sparseOffsetFixture(kind) {
    return fixtureGLB(f=>{
      const a=f.json.accessors[f.indices.move];delete a.bufferView;
      const si=f.add([1],"SCALAR",5123),sv=f.add([0,0.2,0],"VEC3",5126);
      const indices={bufferView:f.json.accessors[si].bufferView,componentType:5123},values={bufferView:f.json.accessors[sv].bufferView};
      const part=kind==="indices"?indices:values,v=f.json.bufferViews[part.bufferView],shift=kind==="indices"?1:2;
      v.byteOffset-=shift;v.byteLength+=shift;part.byteOffset=shift;
      a.sparse={count:1,indices,values};
    });
  }
  test("sparse index offsets cannot compensate misalignment",sparseOffsetFixture("indices"),"SPARSE_BOUNDS");
  test("sparse value offsets cannot compensate misalignment",sparseOffsetFixture("values"),"SPARSE_BOUNDS");
  test("byteStride cannot exceed byteLength",fixtureGLB(f=>{
    const a=f.add([1],"SCALAR",5126);f.json.bufferViews[f.json.accessors[a].bufferView].byteStride=8;
  }),"VIEW_STRIDE");
  test("inverse bind bufferView must not define byteStride",fixtureGLB(f=>{
    f.json.bufferViews[f.json.accessors[f.indices.ib].bufferView].byteStride=64;
  }),"NON_VERTEX_STRIDE");
  test("animation bufferView must not define byteStride",fixtureGLB(f=>{
    f.json.bufferViews[f.json.accessors[f.indices.time].bufferView].byteStride=4;
  }),"NON_VERTEX_STRIDE");
  test("index bufferView must not define byteStride",fixtureGLB(f=>{
    const a=f.add([0,0,1,0,2,0],"SCALAR",5123);f.json.accessors[a].count=3;
    f.json.bufferViews[f.json.accessors[a].bufferView].byteStride=4;f.json.meshes[0].primitives[0].indices=a;
  }),"NON_VERTEX_STRIDE");
  test("sparse value bufferView must not define byteStride",fixtureGLB(f=>{
    const a=f.json.accessors[f.indices.move];delete a.bufferView;
    const si=f.add([1],"SCALAR",5125),sv=f.add([0,0.2,0],"VEC3",5126);
    f.json.bufferViews[f.json.accessors[sv].bufferView].byteStride=12;
    a.sparse={count:1,indices:{bufferView:f.json.accessors[si].bufferView,componentType:5125},values:{bufferView:f.json.accessors[sv].bufferView}};
  }),"SPARSE_BOUNDS");
  function quantizedFixture(componentType,valid) {
    return fixtureGLB(f=>{
      const max=componentType===5121?255:65535,half=Math.floor(max/2);
      const a=f.add([half,valid?max-half:half,0,0,max,0,0,0,half,max-half,0,0],"VEC4",componentType);
      f.json.accessors[a].normalized=true;f.json.meshes[0].primitives[0].attributes.WEIGHTS_0=a;
    });
  }
  test("UINT16 quantized weight sum must be exactly 65535",quantizedFixture(5123,false),"SKIN_QUANTIZED_WEIGHT_SUM");
  test("exact UINT16 quantized weights are accepted",quantizedFixture(5123,true),null);
  test("UINT8 quantized weight sum must be exactly 255",quantizedFixture(5121,false),"SKIN_QUANTIZED_WEIGHT_SUM");
  test("exact UINT8 quantized weights are accepted",quantizedFixture(5121,true),null);
  test("duplicate positively weighted joint slots are rejected",fixtureGLB(f=>patchFixtureScalar(f,f.indices.ji,1,0)),"SKIN_DUPLICATE_JOINT");
  test("extra legal inverse bind matrices are accepted",fixtureGLB(f=>{
    const matrix=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1];
    f.json.skins[0].inverseBindMatrices=f.add([...matrix,...matrix,...matrix,...matrix],"MAT4",5126);
  }),null);
  return {ok:results.every(r=>r.passed),testCount:results.length,results};
}

/**
 * CLI (Node.js 18+):
 *   node scripts/validate-avatar-production-glb.mjs --self-test
 *   node scripts/validate-avatar-production-glb.mjs male.glb female.glb
 *   node scripts/validate-avatar-production-glb.mjs --compact male.glb
 *
 * Reads files only; never rewrites an asset or creates an output file.
 * Exit codes: 0 = checks pass, 1 = validation/self-test failure,
 * 2 = invalid arguments, unreadable input, or unexpected internal failure.
 * JSON is written to stdout. No dependencies or network access are required.
 */
const CLI_HELP = [
  "Read-only production avatar GLB checker (Node.js 18+)",
  "",
  "Usage:",
  "  node validate-avatar-production-glb.mjs [--compact] FILE.glb [FILE.glb ...]",
  "  node validate-avatar-production-glb.mjs [--compact] --self-test",
  "",
  "Required clips: idle, wave, celebrate (names compared case-insensitively).",
  "Checks four-weight skinning, joint palettes, accessors and real non-root clip motion.",
  "Does not replace rendered/browser checks or source-rig influence-loss review.",
  "Exit codes: 0 pass; 1 validation failure; 2 usage/read/internal error."
].join("\n");

async function runCLI(args) {
  let compact = false, selfTest = false, help = false;
  const files = [], bad = [];
  for (const arg of args) {
    if (arg === "--compact") compact = true;
    else if (arg === "--self-test") selfTest = true;
    else if (arg === "--help" || arg === "-h") help = true;
    else if (arg.startsWith("-")) bad.push(arg);
    else files.push(arg);
  }
  const print = value => process.stdout.write(JSON.stringify(value, null, compact ? 0 : 2) + "\n");
  if (help && !bad.length && !files.length && !selfTest) {
    process.stdout.write(CLI_HELP + "\n"); return 0;
  }
  if (bad.length || help || (selfTest && files.length) || (!selfTest && !files.length)) {
    print({ok:false, error:"USAGE", unknownOptions:bad, message:CLI_HELP}); return 2;
  }
  if (selfTest) {
    const result = runSelfTests();
    print({mode:"self-test", ...result});
    return result.ok ? 0 : 1;
  }
  const {readFile} = await import("node:fs/promises");
  const reports = [];
  let exitCode = 0;
  for (const file of files) {
    let bytes;
    try { bytes = await readFile(file); }
    catch (error) {
      reports.push({file, ok:false, error:"READ_FAILED", message:String(error.message)});
      exitCode = 2; continue;
    }
    try {
      const report = validateAvatarGLB(bytes);
      reports.push({file, ...report});
      if (!report.ok && exitCode === 0) exitCode = 1;
    } catch (error) {
      reports.push({file, ok:false, error:"CHECKER_INTERNAL_ERROR", message:String(error.message)});
      exitCode = 2;
    }
  }
  print({ok:exitCode === 0, mode:"files", files:reports, exitCode});
  return exitCode;
}

// Importing this module exposes the pure checker without reading a file.
if (typeof process !== "undefined" && process.versions?.node && process.argv[1]) {
  const {resolve} = await import("node:path");
  const {fileURLToPath} = await import("node:url");
  if (resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
    try { process.exitCode = await runCLI(process.argv.slice(2)); }
    catch (error) {
      process.stdout.write(JSON.stringify({ok:false, error:"CHECKER_INTERNAL_ERROR", message:String(error.message)}) + "\n");
      process.exitCode = 2;
    }
  }
}

