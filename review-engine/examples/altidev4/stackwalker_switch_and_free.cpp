/*
Source excerpt:
- /home/et16/work/altidev4/tsrc/id/windump/StackWalker.cpp
- lines: 640-700
*/

          if (vData != NULL)
          {
            if (GetFileVersionInfoA(szImg, dwHandle, dwSize, vData) != 0)
            {
              UINT len;
              TCHAR szSubBlock[] = _T("\\");
              if (VerQueryValue(vData, szSubBlock, (LPVOID*) &fInfo, &len) == 0)
                fInfo = NULL;
              else
              {
                fileVersion = ((ULONGLONG)fInfo->dwFileVersionLS) + ((ULONGLONG)fInfo->dwFileVersionMS << 32);
              }
            }
            free(vData);
          }
        }
      }

      // Retrive some additional-infos about the module
      IMAGEHLP_MODULE64_V2 Module;
      const char *szSymType = "-unknown-";
      if (this->GetModuleInfo(hProcess, baseAddr, &Module) != FALSE)
      {
        switch(Module.SymType)
        {
          case SymNone:
            szSymType = "-nosymbols-";
            break;
          case SymCoff:
            szSymType = "COFF";
            break;
          case SymCv:
            szSymType = "CV";
            break;
          case SymPdb:
            szSymType = "PDB";
            break;
          case SymExport:
            szSymType = "-exported-";
            break;
          case SymDeferred:
            szSymType = "-deferred-";
            break;
          case SymSym:
            szSymType = "SYM";
            break;
          case 8: //SymVirtual:
            szSymType = "Virtual";
            break;
          case 9: // SymDia:
            szSymType = "DIA";
            break;
        }
      }
      this->m_parent->OnLoadModule(img, mod, baseAddr, size, result, szSymType, Module.LoadedImageName, fileVersion);
    }
    if (szImg != NULL) free(szImg);
    if (szMod != NULL) free(szMod);
    return result;
  }
public:
