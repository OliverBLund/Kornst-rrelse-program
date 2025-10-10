Attribute VB_Name = "Module08dZunker"

Public Sub dZunker(ps, mr, mf, pp, sc, de)
Dim i As Integer
Dim invde As Double '1/de

If ps(sc) < 0.0025 Then
    invde = 3# / 2# * (pp(sc) - pp(sc + 1)) / 100# / 0.0025
Else
    invde = 0
End If

i = 1
Do Until i = sc
    invde = invde + (pp(i) - pp(i + 1)) / 100 * (ps(i) - ps(i + 1)) / (ps(i) * ps(i + 1) * Log(ps(i) / ps(i + 1)))
    i = i + 1
Loop

de = 1 / invde
Range("l17").Value = de
End Sub
