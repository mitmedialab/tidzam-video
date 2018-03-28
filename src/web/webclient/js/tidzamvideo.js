
var addr = window.location.host.split("/")
const websocket_url = "ws://"+addr[0]+"/video-ws/"


var connectionInfoID = 'connectionInfo'
var debugDiv = 'debug'
//requires bson: https://github.com/muhmi/javascript-bson

var bson = new BSON()

var videoInfos = {}
var fullScreen = null //the current fullscreen canvas

function connect() {
  var sck = new WebSocket(websocket_url)
  sck.onopen = function() {
    setState("Connected", "#6ecc5b")
    document.getElementById('connectionErrorText').style.display = "none"
  }

  sck.onclose = function() {
    //setState("Disconnected", "#cc5b5b")
    console.log("here")
    //closeFullScreen()
    //displayError()
  }

  sck.onmessage = function(evt) {
    console.log(evt.data)
    try {

      blobToBuffer(evt.data, function(err, buff) {
        var packet = bson.deserialize(buff)
        handleCameraPacket(packet)
      })

      }catch(e) {
        console.log(e)
    }
  }
  return false
}

function blobToBuffer (blob, cb) {
  if (typeof Blob === 'undefined' || !(blob instanceof Blob)) {
    throw new Error('first argument must be a Blob')
  }
  if (typeof cb !== 'function') {
    throw new Error('second argument must be a function')
  }

  var reader = new FileReader()

  function onLoadEnd (e) {
    reader.removeEventListener('loadend', onLoadEnd, false)
    if (e.error) cb(e.error)
    else cb(null, buffer.Buffer.from(reader.result))
  }

  reader.addEventListener('loadend', onLoadEnd, false)
  reader.readAsArrayBuffer(blob)
}

/**
  Show the current websocket connection state
*/
function setState(txt, color) {
  document.getElementById(connectionInfoID).innerHTML = "<font color='"+color+"'><b>Status: "+txt+"</b></font>"
}

function humanFileSize(bytes, si) {
    var thresh = si ? 1000 : 1024;
    if(Math.abs(bytes) < thresh) {
        return bytes + ' B';
    }
    var units = si
        ? ['kB','MB','GB','TB','PB','EB','ZB','YB']
        : ['KiB','MiB','GiB','TiB','PiB','EiB','ZiB','YiB'];
    var u = -1;
    do {
        bytes /= thresh;
        ++u;
    } while(Math.abs(bytes) >= thresh && u < units.length - 1);
    return bytes.toFixed(1)+' '+units[u];
}

/**
  Update the video information
*/
function updateVideoInfos(meta) {
  let infos = videoInfos[meta.from]

  if(infos == null || infos == undefined) {
    infos = {
      'frameCount': 0,
      'lastUpdate': 0,
      'bytesCount': 0
    }

    videoInfos[meta.from] = infos
  }

  if(meta['detection'] == undefined) {
    boxes = 0
  } else {
    boxes = meta['detection'].length
  }

  infos['frameCount'] += 1
  infos['bytesCount'] += meta['binLen']
  let ellapsed = (Date.now() - infos['lastUpdate'])/1000
  if(ellapsed > 1) {

    if(fullScreen == formatVideoName(meta.from)) {
      document.getElementById('boxes-counter').innerHTML = "Detected "+boxes+" element(s)"
      document.getElementById('fps-counter').innerHTML = "BPS: "+(infos['frameCount']/ellapsed).toFixed(2)
      document.getElementById('bytes-counter').innerHTML = "Brandwidth (total): "+humanFileSize((infos['bytesCount']/ellapsed), true)+"/s"
    }

    infos['frameCount'] = 0 //boxing packets per seconds
    infos['bytesCount'] = 0
    infos['lastUpdate'] = Date.now()

  }
}

function formatVideoName(name) {
  return name.replace(/\./g,"_").replace(/-/g,"_").replace(/ /g,"_").replace("tidzam-video","")
}

function handleCameraPacket(packet) {
  let image  = packet.img
  let meta   = packet.meta

  let canvas = getOrMakeCanvas(packet)

  updateVideoInfos(meta)
  handlePacket(packet)

  //old
  /*drawOnCanvas(canvas, image.buffer).then( () => {

  });*/

}

function drawDetectionData(packet, canvas) {
  let meta = packet.meta

  let box_size_factor_x = canvas.width / meta.shape[1]
  let box_size_factor_y = canvas.height  / meta.shape[0]

  for(let box in meta.detection) {
    box = meta.detection[box]

    //canvas, x, y, w, h, color, label
    let coords = box[2]

    let w = parseInt(box_size_factor_x * (coords[2]))
    let h = parseInt(box_size_factor_y * (coords[3]))

    let x = parseInt(box_size_factor_x * coords[0] - w/2)
    let y = parseInt(box_size_factor_y * coords[1] - h/2)

    let precision = (box[1]*100).toString().substring(0, 5)

    drawBoxInfo(canvas, x, y, w, h, "#"+box[0].toHexColour(), box[0]+" "+precision+"%")
  }
}

/**
  Get a canvas object on the page from a packet
*/
function getOrMakeCanvas(packet, ensureVideo = true) {
  let canvas_id = "canvas_"+formatVideoName(packet.meta.from)
  var canvas = document.getElementById(canvas_id)

  if(canvas != null)
    return canvas

  if(ensureVideo)
    getOrMakeVideo(packet)

  canvas = document.createElement("canvas")
  canvas.setAttribute("id", canvas_id)
  canvas.setAttribute('width', 1080)
  canvas.setAttribute('height', 720)

  canvas.onclick = function() {
    fullScreen = formatVideoName(packet.meta.from)
    imageOnClick(canvas)
  }

  let galery_element = document.createElement('div')
  galery_element.setAttribute('class', 'gallery-element')
  galery_element.appendChild(canvas)

  document.getElementById('gallery').appendChild(galery_element)
  return canvas

}

function drawBoxInfo(canvas, x, y, w, h, color, label, thickWidthPercent = 0.5) {
  let ctx = canvas.getContext("2d")
  ctx.strokeStyle = color
  ctx.lineWidth = parseInt((thickWidthPercent/100) * canvas.width)
  ctx.strokeRect(x, y, w, h)

  drawTextBG(canvas, label, color, x - ctx.lineWidth / 2, y - ctx.lineWidth, w, h) //ecrire label
}

/**
  Draws a text element on a canvas with a filled rectangle in the background
  @param {canvas} canvas: the canvas where the text will me drawn
  @param {string} txt: the string to draw
  @param {string} color the hexa string of the color (#0000 to #FFFF)
  @param {int}    x, y, w, h: the top left coordinates and width and height
  @param {int}    fontWidthPercent the factor of the font size, the font will be rendered with a proportional size to the canvas size
*/
function drawTextBG(canvas, txt, color, x, y, w, h, fontWidthPercent = 2) {
    var ctx = canvas.getContext('2d')
    var fontSize = parseInt(fontWidthPercent/100 * canvas.width)

    ctx.font = "bold "+fontSize+"px Verdana"
    var width = ctx.measureText(txt).width;

    if(x + w/2 < canvas.width/2)
      x += w - width

    if(y + h/2 < canvas.height/2)
      y += h

    ctx.textBaseline = 'top';
    ctx.fillStyle = color;

    ctx.fillRect(x, y - fontSize, width, fontSize + 6);
    ctx.fillStyle = '#000';
    //console.log(brightnessByColor(color))
    if(brightnessByColor(color) < 120)
      ctx.fillStyle = '#FFF'
    ctx.fillText(txt, x, y - fontSize);
}

/**
  Draw an image on a canvas object
  @param {canvas} canvas: the canvas where to draw the image
  @param {uInt8Array} img: the image in bytes

  @return; Promise that concludes when image has been drawn
*/
function drawOnCanvas(canvas, img) {
  // FROM https://stackoverflow.com/questions/21434167/how-to-draw-an-image-on-canvas-from-a-byte-array-in-jpeg-or-png-format

  "use strict";
  var ctx = canvas.getContext("2d");

  //var uInt8Array = new Uint8Array(imgData);
  var uInt8Array = img;

  var i = uInt8Array.length;
  var binaryString = [i];
  while (i--) {
      binaryString[i] = String.fromCharCode(uInt8Array[i]);
  }
  var data = binaryString.join('');
  var base64 = window.btoa(data);

  var img = new Image();
  img.src = "data:image/jpeg;base64," + base64;

  return new Promise( (resolve, reject) => {
    img.onload = function () {
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
        resolve()
    };

    img.onerror = function (stuff) {
        reject(stuff)
    };

  });
}


function hashCode(str) {
    var hash = 0;
    for (var i = 0; i < str.length; i++) {
        hash = str.charCodeAt(i) + ((hash << 5) - hash);
    }
    return hash;
}

// Convert an int to hexadecimal with a max length
// of six characters.
function intToARGB(i) {
    var hex = ((i>>24)&0xFF).toString(16) +
            ((i>>16)&0xFF).toString(16) +
            ((i>>8)&0xFF).toString(16) +
            (i&0xFF).toString(16);
    // Sometimes the string returned will be too short so we
    // add zeros to pad it out, which later get removed if
    // the length is greater than six.
    hex += '000000';
    return hex.substring(0, 6);
}

// Extend the string type to allow converting to hex for quick access.
String.prototype.toHexColour = function() {
    return intToARGB(hashCode(this));
}

/**
 * Calculate brightness value by RGB or HEX color.
 * @param color (String) The color value in RGB or HEX (for example: #000000 || #000 || rgb(0,0,0) || rgba(0,0,0,0))
 * @returns (Number) The brightness value (dark) 0 ... 255 (light)
 */
function brightnessByColor (color) {
  var color = "" + color, isHEX = color.indexOf("#") == 0, isRGB = color.indexOf("rgb") == 0;
  if (isHEX) {
    var m = color.substr(1).match(color.length == 7 ? /(\S{2})/g : /(\S{1})/g);
    if (m) var r = parseInt(m[0], 16), g = parseInt(m[1], 16), b = parseInt(m[2], 16);
  }
  if (isRGB) {
    var m = color.match(/(\d+){3}/g);
    if (m) var r = m[0], g = m[1], b = m[2];
  }
  if (typeof r != "undefined") return ((r*299)+(g*587)+(b*114))/1000;
}

////////////////// Graphic
var modal = document.getElementById('myModal');
var modalImg = document.getElementsByClassName("modal-content")[0];
function imageOnClick(el, is_image = false){
    modal.style.display = "block";
    modalImg.id = el.id;
    document.getElementById("video_"+fullScreen).volume = 1
}
var span_close = document.getElementsByClassName("close")[0];
span_close.onclick = closeFullScreen

function closeFullScreen() {
  if(fullScreen == null) return
  modal.style.display = "none";
  modalImg.id = ""
  document.getElementById("video_"+fullScreen).volume = 0
  fullScreen = null
}
