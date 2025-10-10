Attribute VB_Name = "Module18Zunker"


Public Sub Zunker(T, C, n, fn, de, g, P, u, K)
C = 0.00155
Range("v2").Value = "Zunker"
Range("v3").Value = C
n = Range("n10").Value
fn = (n / (1 - n)) ^ 2
de = Range("l17").Value
de = de / 10# 'convert to cm from mm

K = g * P / u * C * fn * de ^ 2

Range("h27").Value = K
Range("v2").Value = "Zunker"
Range("v3").Value = 0.00155

'Test for suitability
If Application.WorksheetFunction.Min(ActiveSheet.Range("b8:b108")) > 0.0025 Then 'no fraction finer than 0.0025 mm
    ActiveSheet.Cells(2, 27).Copy
    ActiveSheet.Cells(27, 6).Select
    ActiveSheet.Paste
End If
End Sub
