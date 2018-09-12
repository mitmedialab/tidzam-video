
var BSON            = require('bson');
var bson_codec  = new BSON();

window.bson_decode = function(bson_msg){
  json      = bson_codec.deserialize(Buffer.from(bson_msg))
  if (json.img)
    json.img  = new Blob([json.img.buffer]) // This increase the size of json.bin whereas it is in the right size
  return json
}
