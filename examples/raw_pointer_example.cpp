#include <stdio.h>

void smpRawPointer(void)
{
    int* sPtr = new int(42);
    free(sPtr);
    // wrong comment style
}
