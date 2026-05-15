// GreetUI — boot greeter. Welcome chrome around a password field
// driven by the Python GreetController (which round-trips greetd).
//
// Visual parity with qdlocker/qml/LockUI.qml — same NText/NIcon
// widgets from qdshell, same palette, just different copy and a
// session-creation path instead of unlock.

import QtQuick
import QtQuick.Layouts
import qs.Commons
import qs.Widgets

Item {
  id: root
  property var controller

  Rectangle {
    anchors.fill: parent
    color: Color.mSurface
  }

  ColumnLayout {
    anchors.centerIn: parent
    spacing: Style.marginXL
    width: Math.min(parent.width * 0.5, 520)

    NIcon {
      icon: "user-circle"
      pointSize: Style.fontSizeXXL * 2
      color: Color.mPrimary
      Layout.alignment: Qt.AlignHCenter
    }

    NText {
      text: "Welcome to qdistro"
      pointSize: Style.fontSizeXXL
      color: Color.mOnSurface
      Layout.alignment: Qt.AlignHCenter
    }

    NText {
      text: "Sign in as admin"
      pointSize: Style.fontSizeL
      color: Color.mOnSurfaceVariant
      Layout.alignment: Qt.AlignHCenter
    }

    Rectangle {
      Layout.fillWidth: true
      height: 48
      radius: Style.radiusM
      color: Color.mSurfaceVariant
      border.width: passwordInput.activeFocus ? 2 : 1
      border.color: passwordInput.activeFocus ? Color.mPrimary : Color.mOutline

      TextInput {
        id: passwordInput
        anchors.fill: parent
        anchors.leftMargin: Style.marginM
        anchors.rightMargin: Style.marginM
        verticalAlignment: TextInput.AlignVCenter
        font.pointSize: Style.fontSizeL
        color: Color.mOnSurface
        echoMode: TextInput.Password
        passwordCharacter: "•"
        enabled: controller && !controller.busy
        text: controller ? controller.currentText : ""
        onTextChanged: if (controller) controller.currentText = text
        Keys.onPressed: function (event) {
          if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
            controller.submit()
            event.accepted = true
          }
        }
        Component.onCompleted: forceActiveFocus()
      }
    }

    NText {
      visible: controller && controller.statusMessage.length > 0
      text: controller ? controller.statusMessage : ""
      color: Color.mError
      pointSize: Style.fontSizeM
      Layout.alignment: Qt.AlignHCenter
    }

    Loader {
      active: controller && controller.busy
      sourceComponent: NBusyIndicator { }
      Layout.alignment: Qt.AlignHCenter
    }
  }
}
