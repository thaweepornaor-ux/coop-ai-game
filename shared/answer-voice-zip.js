/** Extract the fifteen R01–R15 MP3 answer/reveal files directly from ZIP.
 * Reads ZIP central-directory metadata, including archives using data descriptors.
 * Does not require adding a third-party dependency to the game bundle. */
export async function unpackAnswerVoiceZip(input) {
  if (!input || typeof input.arrayBuffer !== 'function') throw new Error('กรุณาเลือกไฟล์ ZIP เสียงพากย์');
  if (input.size > 40_000_000) throw new Error('ZIP มีขนาดใหญ่เกิน 40 MB');
  const bytes=await input.arrayBuffer(),view=new DataView(bytes);
  let eocd=-1;
  for(let p=view.byteLength-22;p>=Math.max(0,view.byteLength-65557);p--){
    if(view.getUint32(p,true)===0x06054b50){eocd=p;break;}
  }
  if(eocd<0)throw new Error('ไม่พบรายการไฟล์ภายใน ZIP');
  const count=view.getUint16(eocd+10,true);
  let ptr=view.getUint32(eocd+16,true);
  if(count>80||count<15||ptr>=view.byteLength)throw new Error('ZIP ไม่มีไฟล์เสียงครบ 15 ข้อ');
  const files=new Map(),decoder=new TextDecoder();
  for(let i=0;i<count;i++){
    if(ptr+46>view.byteLength||view.getUint32(ptr,true)!==0x02014b50)throw new Error('ข้อมูลไฟล์ ZIP ไม่สมบูรณ์');
    const flags=view.getUint16(ptr+8,true),method=view.getUint16(ptr+10,true);
    const compressedSize=view.getUint32(ptr+20,true),extractedSize=view.getUint32(ptr+24,true);
    const nameLen=view.getUint16(ptr+28,true),extrasLen=view.getUint16(ptr+30,true),commentLen=view.getUint16(ptr+32,true);
    const localOffset=view.getUint32(ptr+42,true),end=ptr+46+nameLen+extrasLen+commentLen;
    if(end>view.byteLength)throw new Error('รายการ ZIP ไม่สมบูรณ์');
    const name=decoder.decode(new Uint8Array(bytes,ptr+46,nameLen)).split(/[/\\]/).at(-1).toUpperCase();
    ptr=end;
    if(!/^R(0[1-9]|1[0-5])\.MP3$/.test(name))continue;
    if(files.has(name))throw new Error('มีไฟล์ '+name+' ซ้ำใน ZIP');
    if(flags&1||![0,8].includes(method))throw new Error('ZIP ต้องไม่มีรหัสผ่าน');
    if(compressedSize>15_000_000||extractedSize<1000||extractedSize>15_000_000)throw new Error('ไฟล์ '+name+' มีขนาดผิดปกติ');
    if(localOffset+30>view.byteLength||view.getUint32(localOffset,true)!==0x04034b50)throw new Error('ส่วนข้อมูลเสียง ZIP ไม่สมบูรณ์');
    const begin=localOffset+30+view.getUint16(localOffset+26,true)+view.getUint16(localOffset+28,true);
    if(begin+compressedSize>view.byteLength)throw new Error('ข้อมูลเสียง ZIP ไม่สมบูรณ์');
    const payload=bytes.slice(begin,begin+compressedSize);
    let expanded;
    if(method===0)expanded=payload;
    else{
      if(typeof DecompressionStream==='undefined')throw new Error('เบราว์เซอร์ไม่รองรับ ZIP นี้ กรุณาแตกไฟล์แล้วเลือก MP3 ทั้ง 15 ไฟล์');
      try{expanded=await new Response(new Blob([payload]).stream().pipeThrough(new DecompressionStream('deflate-raw'))).arrayBuffer();}
      catch{throw new Error('แตกไฟล์ ZIP ไม่สำเร็จ กรุณาลอง Chrome หรือ Edge เวอร์ชันล่าสุด');}
    }
    if(expanded.byteLength!==extractedSize)throw new Error('เสียง '+name+' มีขนาดไม่ตรงกับข้อมูล ZIP');
    files.set(name,new File([expanded],name,{type:'audio/mpeg'}));
  }
  return Array.from({length:15},(_,i)=>{
    const name='R'+String(i+1).padStart(2,'0')+'.MP3',match=files.get(name);
    if(!match)throw new Error('ไม่พบ '+name+' ใน ZIP กรุณาใช้ชุดเสียง 15 ข้อ');
    return match;
  });
}
