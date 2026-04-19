/*
Source excerpt:
- /home/et16/work/altidev4/tsrc/id/windump/mydump.cpp
- lines: 580-610
*/

        }

    } // for ( frameNum )

    if ( gle != 0 )
        printf( "\nStackWalk(): gle = %lu\n", gle );

cleanup:
    ResumeThread( hThread );
    // de-init symbol handler etc. (SymCleanup())
    pSymCleanup( hProcess );
    free( pSym );
    delete [] tt;
}



void enumAndLoadModuleSymbols( HANDLE hProcess, DWORD pid )
{
    ModuleList modules;
    ModuleListIter it;
    char *img, *mod;

    // fill in module list
    fillModuleList( modules, pid, hProcess );

    for ( it = modules.begin(); it != modules.end(); ++ it )
    {
        // unfortunately, SymLoadModule() wants writeable strings
        img = new char[(*it).imageName.size() + 1];
        strcpy( img, (*it).imageName.c_str() );
