#ifndef AppVersion
  #define AppVersion "0.1.0-beta.1"
#endif
#ifndef SourceRoot
  #define SourceRoot ".."
#endif

[Setup]
AppId={{E2EE3608-04CC-43ED-A78E-B86D132D3B67}
AppName=YFPhoneCam
AppVersion={#AppVersion}
AppPublisher=YFPhoneCam contributors
AppPublisherURL=https://github.com/YannikFroehlich/YFPhoneCam
AppSupportURL=https://github.com/YannikFroehlich/YFPhoneCam/issues
AppUpdatesURL=https://github.com/YannikFroehlich/YFPhoneCam/releases
DefaultDirName={autopf}\YFPhoneCam
DefaultGroupName=YFPhoneCam
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
UsedUserAreasWarning=no
OutputDir=output
OutputBaseFilename=YFPhoneCam-Setup-{#AppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
SetupLogging=yes
CloseApplications=force
RestartApplications=no
AppMutex=YFPhoneCam.Desktop.0.1
UninstallDisplayIcon={app}\YFPhoneCam.exe
LicenseFile={#SourceRoot}\LICENSE
InfoAfterFile={#SourceRoot}\docs\INSTALLATION.md
ChangesAssociations=no
DisableProgramGroupPage=yes

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "{#SourceRoot}\dist\YFPhoneCam\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs restartreplace
Source: "{#SourceRoot}\vendor\UnityCapture\UnityCaptureFilter32.dll"; DestDir: "{app}"; Flags: ignoreversion restartreplace
Source: "{#SourceRoot}\vendor\UnityCapture\UnityCaptureFilter64.dll"; DestDir: "{app}"; Flags: ignoreversion restartreplace; AfterInstall: RegisterCameraFilters
Source: "{#SourceRoot}\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceRoot}\THIRD_PARTY_NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceRoot}\licenses\*"; DestDir: "{app}\licenses"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#SourceRoot}\vendor\UnityCapture\LICENSE.Filter.txt"; DestDir: "{app}\licenses\UnityCapture"; Flags: ignoreversion
Source: "{#SourceRoot}\vendor\UnityCapture\LICENSE.SharedProtocol.txt"; DestDir: "{app}\licenses\UnityCapture"; Flags: ignoreversion

[Icons]
Name: "{group}\YFPhoneCam"; Filename: "{app}\YFPhoneCam.exe"; WorkingDir: "{app}"
Name: "{group}\Uninstall YFPhoneCam"; Filename: "{uninstallexe}"
Name: "{autodesktop}\YFPhoneCam"; Filename: "{app}\YFPhoneCam.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\YFPhoneCam.exe"; Description: "Launch YFPhoneCam"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{localappdata}\YFPhoneCam"

[Code]
function RunFilterRegistration(const Regsvr32Path, Arguments: String): Boolean;
var
  ResultCode: Integer;
begin
  Result := Exec(
    ExpandConstant(Regsvr32Path),
    Arguments,
    '',
    SW_HIDE,
    ewWaitUntilTerminated,
    ResultCode
  ) and (ResultCode = 0);
end;

function Register32: Boolean;
begin
  Result := RunFilterRegistration(
    '{syswow64}\regsvr32.exe',
    '/s /i:UnityCaptureName=YFPhoneCam "' + ExpandConstant('{app}\UnityCaptureFilter32.dll') + '"'
  );
end;

function Register64: Boolean;
begin
  Result := RunFilterRegistration(
    '{sys}\regsvr32.exe',
    '/s /i:UnityCaptureName=YFPhoneCam "' + ExpandConstant('{app}\UnityCaptureFilter64.dll') + '"'
  );
end;

function Unregister32: Boolean;
begin
  Result := RunFilterRegistration(
    '{syswow64}\regsvr32.exe',
    '/s /u "' + ExpandConstant('{app}\UnityCaptureFilter32.dll') + '"'
  );
end;

function Unregister64: Boolean;
begin
  Result := RunFilterRegistration(
    '{sys}\regsvr32.exe',
    '/s /u "' + ExpandConstant('{app}\UnityCaptureFilter64.dll') + '"'
  );
end;

procedure RegisterCameraFilters;
begin
  WizardForm.StatusLabel.Caption := 'Registering the YFPhoneCam virtual camera...';
  if not Register32 then
    RaiseException('The 32-bit YFPhoneCam camera could not be registered. Setup was rolled back.');
  if not Register64 then
  begin
    Unregister32;
    RaiseException('The 64-bit YFPhoneCam camera could not be registered. Setup was rolled back.');
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
  begin
    if not Unregister32 then
      RaiseException('The 32-bit YFPhoneCam camera could not be unregistered. Uninstall was stopped.');
    if not Unregister64 then
    begin
      Register32;
      RaiseException('The 64-bit YFPhoneCam camera could not be unregistered. Uninstall was stopped.');
    end;
  end;
end;
