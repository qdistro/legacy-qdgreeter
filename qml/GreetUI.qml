// GreetUI — pure-QtQuick boot greeter, no Quickshell dependency.
//
// Minimal sign-in chrome: username field (auto-filled, read-only —
// single-user qdistro), password field, submit button, error label.
//
// Per plan2/tasks/P01: deliberately minimal — branding polish is
// reserved for a follow-up task. Hardcoded dark-theme palette mirrors
// the colour intent of qdshell without importing qs.Commons/qs.Widgets.
//
// Controller interface (from qdgreeter/controller.py):
//   username, currentText, statusMessage, busy
// with NOTIFY signals; submit() slot.

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
  id: root
  property var controller

  Rectangle {
    anchors.fill: parent
    color: "#101015"
  }

  ColumnLayout {
    anchors.centerIn: parent
    spacing: 24
    width: Math.min(parent.width * 0.5, 520)

    Text {
      text: "👤"
      font.pointSize: 56
      color: "#80c0ff"
      Layout.alignment: Qt.AlignHCenter
    }

    Text {
      text: "Welcome to qdistro"
      font.pointSize: 28
      color: "white"
      Layout.alignment: Qt.AlignHCenter
    }

    // Username field. Auto-filled from controller.username; read-only
    // because qdistro is single-user (admin). Showing it explicitly
    // (vs. just a label) keeps the UI honest about *who* the password
    // is unlocking — the greeter is the only place a future user
    // picker could plausibly live.
    Rectangle {
      Layout.fillWidth: true
      height: 48
      radius: 6
      color: "#202028"
      border.width: 1
      border.color: "#555560"

      TextInput {
        id: usernameInput
        objectName: "qdgreeter.username"
        anchors.fill: parent
        anchors.leftMargin: 12
        anchors.rightMargin: 12
        verticalAlignment: TextInput.AlignVCenter
        font.pointSize: 16
        color: "white"
        readOnly: true
        text: controller ? controller.username : "admin"
      }
    }

    Rectangle {
      Layout.fillWidth: true
      height: 48
      radius: 6
      color: "#202028"
      border.width: passwordInput.activeFocus ? 2 : 1
      border.color: passwordInput.activeFocus ? "#80c0ff" : "#555560"

      TextInput {
        id: passwordInput
        objectName: "qdgreeter.password"
        anchors.fill: parent
        anchors.leftMargin: 12
        anchors.rightMargin: 12
        verticalAlignment: TextInput.AlignVCenter
        font.pointSize: 16
        color: "white"
        echoMode: TextInput.Password
        passwordCharacter: "•"
        enabled: controller ? !controller.busy : false
        text: controller ? controller.currentText : ""
        onTextChanged: if (controller) controller.currentText = text
        Keys.onPressed: function (event) {
          if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
            if (controller) controller.submit()
            event.accepted = true
          }
        }
        Component.onCompleted: forceActiveFocus()
      }
    }

    // Submit button. The Enter key on the password field is the
    // primary path; the button is a fallback for keyboard-less
    // boot situations (touch / fingerprint readers with no kbd).
    Rectangle {
      id: submitButton
      objectName: "qdgreeter.submit"
      Layout.fillWidth: true
      height: 44
      radius: 6
      color: submitMouse.pressed ? "#5090cc" : "#80c0ff"
      opacity: (controller && controller.busy) ? 0.5 : 1.0

      Text {
        anchors.centerIn: parent
        text: "Sign in"
        font.pointSize: 16
        color: "#101015"
      }

      MouseArea {
        id: submitMouse
        anchors.fill: parent
        enabled: controller ? !controller.busy : false
        cursorShape: Qt.PointingHandCursor
        onClicked: if (controller) controller.submit()
      }
    }

    // Error label — visible only when greetd or the controller has
    // something to say. Status comes from controller.statusMessage
    // (auth_error description, info auth_message text, or local
    // exception string).
    Text {
      objectName: "qdgreeter.status"
      visible: controller ? controller.statusMessage.length > 0 : false
      text: controller ? controller.statusMessage : ""
      color: "#ff8080"
      font.pointSize: 14
      Layout.alignment: Qt.AlignHCenter
    }

    BusyIndicator {
      Layout.alignment: Qt.AlignHCenter
      visible: controller ? controller.busy : false
      running: visible
    }
  }
}
