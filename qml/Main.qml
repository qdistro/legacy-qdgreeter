import QtQuick
import QtQuick.Window

Window {
  id: root
  visible: true
  visibility: Window.FullScreen
  color: "#101015"

  GreetUI {
    id: greetUI
    anchors.fill: parent
    controller: controller
  }
}
