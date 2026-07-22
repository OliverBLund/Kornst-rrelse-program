#ifndef AppVersion
#define AppVersion "0.9.7"
#endif

#ifndef SourceDir
#define SourceDir "C:/gsa_build/" + AppVersion + "/GrainSizeAnalysis"
#endif

#ifndef OutputDir
#define OutputDir "C:/gsa_build/" + AppVersion
#endif

#define AppName "Grain Size Analysis"
#define AppExeName "GrainSizeAnalysis.exe"
#define AppPublisher "DTU"
#define AppUrl "https://www.dtu.dk/"
#define IconFile SourceDir + "/r/Program/resources/app_icon.ico"
#define InstalledIconFile "{app}\r\Program\resources\app_icon.ico"
#define LicenseFile SourceDir + "/COPYING"
#define SourceNoticeFile SourceDir + "/SOURCE_CODE_NOTICE.txt"

#ifnexist SourceDir + "/" + AppExeName
  #error "Folder build not found. Build folder mode first, then run BUILD_INSTALLER.bat."
#endif

#ifnexist IconFile
  #define LegacyIconFile SourceDir + "/Program/resources/app_icon.ico"
  #ifexist LegacyIconFile
    #undef IconFile
    #define IconFile LegacyIconFile
    #undef InstalledIconFile
    #define InstalledIconFile "{app}\Program\resources\app_icon.ico"
  #else
    #error "Application icon not found in folder build. Rebuild with the current BUILD_EXE.bat."
  #endif
#endif

#ifnexist LicenseFile
  #error "GPL license file not found in folder build. Rebuild with the current BUILD_EXE.bat."
#endif

#ifnexist SourceNoticeFile
  #error "Source code notice not found in folder build. Rebuild with the current BUILD_EXE.bat."
#endif

[Setup]
AppId={{47D18B9D-03B0-44B9-A52E-D5BB240C3C3C}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppUrl}
AppSupportURL={#AppUrl}
AppUpdatesURL={#AppUrl}
DefaultDirName={localappdata}\Programs\GrainSizeAnalysis
DisableDirPage=no
AlwaysShowDirOnReadyPage=yes
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir={#OutputDir}
OutputBaseFilename=GrainSizeAnalysis-{#AppVersion}-Setup
SetupIconFile={#IconFile}
LicenseFile={#LicenseFile}
InfoBeforeFile={#SourceNoticeFile}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#AppExeName}
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; IconFilename: "{#InstalledIconFile}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; IconFilename: "{#InstalledIconFile}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent
