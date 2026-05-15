import QtQuick
import QtQuick.Window
import qs.Commons
import qs.Widgets

Window {
  id: root
  visible: true
  visibility: Window.FullScreen
  color: Color ? Color.mSurface : "#101015"

  GreetUI {
    id: greetUI
    anchors.fill: parent
    controller: controller
  }
}
