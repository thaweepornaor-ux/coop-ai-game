/** Canonical 2D pose-arm rig. Both bare forearms and corresponding sleeve hems
 * consume these shared definitions so pose transitions cannot silently drift.
 * Geometry is in the approved 160x220 avatar coordinate system. */
export const AVATAR_ARM_RIG=Object.freeze({
  stand:Object.freeze({
    left:Object.freeze({forearm:"M39 118Q37 127 38 139Q37 144 39 146Q41 149 43 148Q47 148 48 143Q49 136 49 124Z",cuff:"M39 118Q43 122 49 124"}),
    right:Object.freeze({forearm:"M121 118Q123 127 122 139Q123 144 121 146Q119 149 117 148Q113 148 112 143Q111 136 111 124Z",cuff:"M121 118Q117 122 111 124"}),
  }),
  wave:Object.freeze({
    left:Object.freeze({forearm:"M30 93Q27 85 25 78Q23 73 24 70Q25 66 28 67Q32 68 34 75Q36 87 39 104Z",cuff:"M30 93Q34 99 39 104"}),
    right:Object.freeze({forearm:"M121 118Q123 127 122 139Q123 144 121 146Q119 149 117 148Q113 148 112 143Q111 136 111 124Z",cuff:"M121 118Q117 122 111 124"}),
  }),
  celebrate:Object.freeze({
    left:Object.freeze({forearm:"M32 88Q30 78 28 69Q26 62 29 59Q31 57 34 59Q37 61 38 67Q37 83 38 102Z",cuff:"M32 88Q35 95 38 102"}),
    right:Object.freeze({forearm:"M128 88Q130 78 132 69Q134 62 131 59Q129 57 126 59Q123 61 122 67Q123 83 122 102Z",cuff:"M128 88Q125 95 122 102"}),
  }),
  think:Object.freeze({
    left:Object.freeze({forearm:"M39 118Q37 127 38 139Q37 144 39 146Q41 149 43 148Q47 148 48 143Q49 136 49 124Z",cuff:"M39 118Q43 122 49 124"}),
    right:Object.freeze({forearm:"M120 118Q124 125 122 130Q120 137 114 138Q109 139 105 133L91 101Q87 96 89 92Q91 87 96 89Q99 90 101 94L114 121L109 124Z",cuff:"M120 118Q116 122 109 124"}),
  }),
  confident:Object.freeze({
    left:Object.freeze({forearm:"M40 118Q38 127 41 134Q44 141 50 142Q54 142 61 138L61 135Q58 132 55 132L49 129L50 124Z",cuff:"M40 118Q44 122 50 124"}),
    right:Object.freeze({forearm:"M120 118Q122 127 119 134Q116 141 110 142Q106 142 99 138L99 135Q102 132 105 132L111 129L110 124Z",cuff:"M120 118Q116 122 110 124"}),
  }),
});

export function armForPose(pose,side){
  const pair=AVATAR_ARM_RIG[pose];
  if(!pair||!Object.hasOwn(pair,side))throw new RangeError('Unknown avatar arm joint');
  return pair[side];
}
