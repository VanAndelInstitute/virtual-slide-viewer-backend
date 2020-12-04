[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$uri = "https://path-uat.cptac.vai.org/CheckFileTransferStatus"
cd D:\Images\CPTAC
$list = ls *.svs | ForEach-Object {@{"filename" = $_.Name; "size" = $_.Length}}
If($list.Count -eq 0)
{
    return
}
$body = @{"files" = $list} | ConvertTo-Json
$result = Invoke-RestMethod -Method 'POST' -Uri $uri -Body $body
ForEach($filename in $result)
{
    del $filename
} 
