// GreetUI — boot greeter. Minimal sign-in chrome:
// username field (auto-filled, read-only — single-user qdistro),
// password field, submit button, error label.
//
// Per plan2/tasks/P01: deliberately minimal — branding polish is
// reserved for a follow-up task. Visuals reuse qdshell's qs.Commons
// (Color, Style) and qs.Widgets (NText, NIcon, NBusyIndicator).

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

    // Username field. Auto-filled from controller.username; read-only
    // because qdistro is single-user (admin). Showing it explicitly
    // (vs. just a label) keeps the UI honest about *who* the password
    // is unlocking — the greeter is the only place a future user
    // picker could plausibly live.
    Rectangle {
      Layout.fillWidth: true
      height: 48
      radius: Style.radiusM
      color: Color.mSurfaceVariant
      border.width: 1
      border.color: Color.mOutline

      TextInput {
        id: usernameInput
        objectName: "qdgreeter.username"
        anchors.fill: parent
        anchors.leftMargin: Style.marginM
        anchors.rightMargin: Style.marginM
        verticalAlignment: TextInput.AlignVCenter
        font.pointSize: Style.fontSizeL
        color: Color.mOnSurface
        readOnly: true
        text: controller ? controller.username : "admin"
      }
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
        objectName: "qdgreeter.password"
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
      radius: Style.radiusM
      color: submitMouse.pressed ? Color.mPrimaryDim : Color.mPrimary
      opacity: (controller && controller.busy) ? 0.5 : 1.0

      NText {
        anchors.centerIn: parent
        text: "Sign in"
        pointSize: Style.fontSizeL
        color: Color.mOnPrimary
      }

      MouseArea {
        id: submitMouse
        anchors.fill: parent
        enabled: controller && !controller.busy
        cursorShape: Qt.PointingHandCursor
        onClicked: if (controller) controller.submit()
      }
    }

    // Error label — visible only when greetd or the controller has
    // something to say. Status comes from controller.statusMessage
    // (auth_error description, info auth_message text, or local
    // exception string).
    NText {
      objectName: "qdgreeter.status"
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
