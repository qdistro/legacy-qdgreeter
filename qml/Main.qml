import QtQuick
import QtQuick.Window
import shim

Window {
  id: root
  visible: true
  visibility: Window.FullScreen
  color: Color.mSurface

  GreetUI {
    id: greetUI
    anchors.fill: parent
    controller: controller
  }
}
