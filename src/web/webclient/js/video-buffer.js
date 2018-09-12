
var global_buffer  = {} //videoid: Packet[]
var videos = {}

function getPacketTime(packet) {
  return eval(packet.meta.frame_count) / eval(packet.meta.meta.frame_rate_processing)
}

function getVideoURL(packet) {
  if (packet.meta.path.indexOf("http") != -1 || packet.meta.path.indexOf("rtsp") != -1)
    return packet.meta.path
  return "https://tidzam.media.mit.edu"+packet.meta.path
}

/**
  Called when disconnectd
*/
function displayError() {
  document.getElementById('connectionErrorText').style.display = "block"
  for(let i in videos) {
    if(i == "fullScreen")
      continue
    videos[i][0].pause()
    displayErrorImage(videos[i][1])
  }
}

var errorImg = new Image();
errorImg.src = "res/disco.png";
function displayErrorImage(canvas) {
    w = errorImg.width
    h = errorImg.height
    canvas.getContext('2d').drawImage(errorImg, (canvas.width -  w)/2, (canvas.height -  h)/2);
}

function getOrMakeVideo(packet) {
  let name = formatVideoName(packet.meta.from)

  let vid = document.getElementById('video_'+name)
  if(vid != null)
    return vid
  //append video to the graveyard
  vid = document.createElement("video")
  vid.id  = "video_"+name
  vid.name = name
  vid.src = getVideoURL(packet)
  vid.type = "video/mp4"
  vid.volume = 0
  vid.autoplay = 1

  vid.addEventListener('ended',videoEndHandler,false);

  document.getElementById("video-garbage").appendChild(vid)
  vid.play()


  return vid
}

function removeStream(name) {
  if(!(name in videos))
    return

  if(fullScreen == name)
    closeFullScreen()

  document.getElementById("video_"+name).remove() //remove video source
  document.getElementById("canvas_"+name).parentElement.remove() //remove canvas
  delete videos[name]
  delete global_buffer["video_"+name]
}

function videoEndHandler(vid) {
  console.log(vid.target.name+" ended")
  removeStream(vid.target.name)
}


/**
  Add the video to the renderer list
*/
function maybeStartVideoRender(packet) {
  if(formatVideoName(packet.meta.from) in videos)
    return

  let video  = getOrMakeVideo(packet)
  let canvas = getOrMakeCanvas(packet)

  videos[formatVideoName(packet.meta.from)] = [video, canvas]
}

/**
  Dumps the global buffer to the console for debugging
*/
function dump_buffer() {
  for(let i in global_buffer) {
    let buffer = global_buffer[i]
    console.log("BUFFER FOR "+i+" "+getOrMakeVideo(buffer[0]).currentTime)
    for(let j in buffer) {
      console.log(getPacketTime(buffer[j])+" "+buffer[j].meta.detection.length)
    }
  }
}

/**
  Adds the packet to the appropriate buffer and sorts it and set the video to the correct time
*/
function handlePacket(packet) {
  //console.log("Packet from "+packet.meta.from+" fid="+packet.meta.frame_count)

  maybeStartVideoRender(packet)

  let video = getOrMakeVideo(packet)
  if(global_buffer[video.id] == undefined)
    global_buffer[video.id] = []

  let buffer = global_buffer[video.id]

  let packet_time =  getPacketTime(packet)
  let video_time  =  video.currentTime


  buffer.push(packet)
  buffer.sort(function(packet1, packet2) {
      return packet1.meta.frame_count - packet2.meta.frame_count;
  });

  if(packet_time < video_time /*|| Math.abs(packet_time - video_time) > 2*/ ) {
    console.log("Video "+video.id+" is restarting at "+packet_time)
    video.currentTime = Math.floor(packet_time)
    video.play()
  }

  //console.log("vido_time="+video_time+" packet_time="+packet_time)
  //console.log("Buffer size is "+buffer.length)
  if(buffer.length > 10)
    console.log("Warn: Buffer is large isn't it ? ("+buffer.length+")")
}

/**
  Cleans the buffer and get the most appropriate packet for the current video time
*/
function getPacketFromBuffer(video) {
  let video_time = video.currentTime
  let lower = Number.MAX_VALUE
  let i = 0

  let buffer = global_buffer[video.id]
  if(buffer.length == 0)
    return null

  while(i < buffer.length) {
    let dist = Math.abs(getPacketTime(buffer[i]) - video_time)

    if( dist  > lower )
      break

    lower = dist
    i++;
  }

  if(i > 1)
    buffer.splice(0, i - 1)

  //console.log("[DEBUG] Buffer size is "+buffer.length)

  return buffer[0]

}


var FPS = 60
var delay = 1000/FPS
function renderVideos() {
  try{
    if(fullScreen != null) {

      if(videos['fullScreen'] == null) {
        videos['fullScreen'] = [document.getElementById("video_"+fullScreen), document.getElementById("canvas_"+fullScreen)]
      }

      renderVideo(videos.fullScreen[0], videos.fullScreen[1], videos.fullScreen[1].width, videos.fullScreen[1].height)
    } else {
      videos['fullScreen'] = null

      for(let i in videos) {
        if(i == "fullScreen")
          continue
        let vid = videos[i][0]
        let canvas = videos[i][1]
        renderVideo(vid, canvas, canvas.width, canvas.height)
      }
    }
  }
  catch(err){
    // TODO
    console.log("error renderVideos")
  }


  setTimeout(function(){ renderVideos(); }, delay);
}

/**
  Render the current image in video into the canvas
*/
function renderVideo(v, canvas, w, h) {

  if(v == null || v == undefined) return false;

  if(v.paused || v.ended) return false;
  ctx = canvas.getContext('2d')

  ctx.drawImage(v,0,0,w,h);
  drawDetectionData(getPacketFromBuffer(v), canvas)
}

renderVideos()
console.log("Renderer started")
