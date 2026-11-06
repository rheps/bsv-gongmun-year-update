# 이 도구가 띄운 한글의 창(WPF)이 「파일 접근 확인」 창이고 「접근 허용 : ALT+Y」 단추가 있는지만 확인한다(hwpcom.py 감시기가 부름).
# 누르기는 hwpcom.py가 그 창에 Alt+Y를 보내서 한다(UI Automation Invoke로는 창이 닫히지 않음, 2026-11-05 확인). 「모두 허용」은 누르지 않는다.
param([Parameter(Mandatory=$true)][long]$Hwnd)
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$el = [System.Windows.Automation.AutomationElement]::FromHandle([IntPtr]$Hwnd)
if ($null -eq $el) { Write-Output "no-window"; exit 1 }
$cond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty, [System.Windows.Automation.ControlType]::Button)
$texts = @()
foreach ($x in $el.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition)) { $texts += $x.Current.Name }
$msg = ($texts -join ' ')
if ($msg -notmatch '접근') { Write-Output "not-access-dialog"; exit 2 }
foreach ($b in $el.FindAll([System.Windows.Automation.TreeScope]::Descendants, $cond)) {
    if ($b.Current.Name -like '접근 허용*ALT+Y*') {
        Write-Output "access-dialog"
        exit 0
    }
}
Write-Output "no-button"; exit 3
