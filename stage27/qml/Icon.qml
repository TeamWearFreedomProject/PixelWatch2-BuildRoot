import QtQuick 2.12

Canvas {
    id: icon
    width: 28
    height: 28
    property string kind: "clock"
    property color ink: "white"
    onKindChanged: requestPaint()
    onInkChanged: requestPaint()
    onPaint: {
        var c = getContext("2d")
        c.reset()
        c.scale(width / 32, height / 32)
        c.strokeStyle = ink
        c.fillStyle = ink
        c.lineWidth = 2.2
        c.lineCap = "round"
        c.lineJoin = "round"
        function line(x, y, a, b) { c.beginPath(); c.moveTo(x,y); c.lineTo(a,b); c.stroke() }
        function ring(x, y, r) { c.beginPath(); c.arc(x,y,r,0,Math.PI*2); c.stroke() }
        function dot(x, y, r) { c.beginPath(); c.arc(x,y,r,0,Math.PI*2); c.fill() }
        if (kind === "clock") {
            ring(16,16,11); line(16,9,16,16); line(16,16,22,19)
        } else if (kind === "stopwatch") {
            ring(16,18,10); line(13,3,19,3); line(16,3,16,7)
            line(24,7,27,10); line(16,12,16,18); line(16,18,20,18)
        } else if (kind === "timer") {
            ring(16,17,10); line(12,3,20,3); line(16,3,16,7)
            line(16,11,16,17); line(16,17,12,20)
        } else if (kind === "calculator") {
            c.strokeRect(6,3,20,26); line(10,10,22,10)
            for (var x=11;x<=21;x+=10) for (var y=16;y<=24;y+=8) dot(x,y,1.3)
        } else if (kind === "light") {
            c.beginPath(); c.moveTo(7,4); c.lineTo(25,4); c.lineTo(20,13)
            c.lineTo(20,28); c.lineTo(12,28); c.lineTo(12,13); c.closePath(); c.stroke()
            line(12,13,20,13); line(16,19,16,22)
        } else if (kind === "style") {
            ring(16,16,11); dot(12,11,1.4); dot(21,12,1.4); dot(10,19,1.4); dot(19,22,2.5)
        } else if (kind === "about") {
            ring(16,16,11); dot(16,10,1.2); line(16,15,16,23)
        } else if (kind === "apps") {
            for (var a=0;a<3;a++) for (var b=0;b<3;b++) dot(8+a*8,8+b*8,1.8)
        } else if (kind === "back") {
            line(19,7,10,16); line(10,16,19,25)
        }
    }
}
