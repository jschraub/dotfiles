/* Select a PAM branch, never authenticate a user or handle an auth token. */
#include <glob.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <security/pam_ext.h>
#include <security/pam_modules.h>

#ifndef ATELIER_LID_PATTERN
#define ATELIER_LID_PATTERN "/proc/acpi/button/lid/*/state"
#endif

static int lid_closed(void) {
    glob_t paths = {0};
    int result = glob(ATELIER_LID_PATTERN, 0, NULL, &paths);
    int closed = result != 0 && result != GLOB_NOMATCH;
    if (result == 0) {
        for (size_t i = 0; i < paths.gl_pathc; ++i) {
            char state[128];
            FILE *file = fopen(paths.gl_pathv[i], "r");
            if (file == NULL) {
                closed = 1;
                break;
            }
            if (fgets(state, sizeof(state), file) == NULL || strstr(state, "open") == NULL)
                closed = 1;
            fclose(file);
            if (closed) break;
        }
    }
    globfree(&paths);
    return closed;
}

PAM_EXTERN int pam_sm_authenticate(pam_handle_t *pamh, int flags, int argc, const char **argv) {
    (void)flags; (void)argc; (void)argv;
    char *choice = NULL;
    /* Mask even this public choice so an older greeter cannot expose a password
     * accidentally typed in response to an unfamiliar selector prompt. */
    int result = pam_prompt(pamh, PAM_PROMPT_ECHO_OFF, &choice, "Atelier authentication method:");
    if (result != PAM_SUCCESS || choice == NULL) {
        free(choice);
        return PAM_AUTH_ERR;
    }
    if (strcmp(choice, "password") == 0)
        result = PAM_IGNORE;
    else if (strcmp(choice, "fingerprint") == 0)
        result = lid_closed() ? PAM_IGNORE : PAM_SUCCESS;
    else
        result = PAM_AUTH_ERR;
    free(choice);
    return result;
}

PAM_EXTERN int pam_sm_setcred(pam_handle_t *pamh, int flags, int argc, const char **argv) {
    (void)pamh; (void)flags; (void)argc; (void)argv;
    return PAM_SUCCESS;
}
