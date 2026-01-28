#Requires AutoHotkey v2.0
#SingleInstance Force

; --- Создаем GUI (графический интерфейс пользователя) ---
MyGui := Gui()
MyGui.Opt("+AlwaysOnTop -Caption +ToolWindow")
MyGui.BackColor := "Black"
MyGui.AddText("w800 cWhite Center", "Кликните левой кнопкой мыши в нужном месте экрана.`nНажмите ESC для отмены.").SetFont("s20")
MyGui.Show("Maximize")
WinSetTransparent(120, MyGui)

; --- Активируем горячие клавиши ---
Hotkey "~LButton", OnLeftClick
Hotkey "~Escape", OnEscape
Return ; Завершаем автоматическую часть скрипта

; --- Функции-обработчики ---
OnLeftClick(*) {
    CoordMode "Mouse", "Screen"
    MouseGetPos(&MouseX, &MouseY)
    A_Clipboard := MouseX "," MouseY
    ExitApp
}

OnEscape(*) {
    A_Clipboard := "" ; Очищаем буфер обмена, чтобы Python знал об отмене
    ExitApp
}

