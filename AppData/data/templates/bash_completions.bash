#!/bin/bash

# It would have been impossible to create this without the following post on Stack Exchange!!!
# https://unix.stackexchange.com/a/55622

type "{executable_name}" &> /dev/null &&
_get_app_ids_{current_date}(){
    echo $(cd {full_path_to_app_folder}; ./app.py print_app_ids)
} &&
_decide_nospace_{current_date}(){
    if [[ ${1} == "--"*"=" ]] ; then
        type "compopt" &> /dev/null && compopt -o nospace
    fi
} &&
_user_applications_manager_cli_{current_date}(){
    local cur prev cmd app_ids app_types
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    prev_to_prev="${COMP_WORDS[COMP_CWORD-2]}"
    app_types=("git_repo" "hg_repo" "file" "archive")

    case $prev in
        "--id")
            app_ids=( $(_get_app_ids_{current_date}) )
            COMPREPLY=( $( compgen -W "${app_ids[*]}") )
            return 0
            ;;
        "-i")
            app_ids=( $(_get_app_ids_{current_date}) )
            COMPREPLY=( $( compgen -W "${app_ids[*]}" -- ${cur}) )
            return 0
            ;;
        "--type"|"--type=")
            COMPREPLY=( $( compgen -W "${app_types[*]}") )
            _decide_nospace_{current_date} ${COMPREPLY[0]}
            return 0
            ;;
        "-t")
            COMPREPLY=( $( compgen -W "${app_types[*]}" -- ${cur}) )
            return 0
            ;;
    esac

    # Handle auto-completion of long options items ending with equal sign.
    if [[ ${prev} == "=" ]] ; then
        if [[ ${cur} != *"/"* ]]; then
            case $prev_to_prev in
                "--id")
                    app_ids=( $(_get_app_ids_{current_date}) )
                    COMPREPLY=( $( compgen -W "${app_ids[*]}" -- ${cur}) )
                    return 0
                    ;;
                "--type")
                    COMPREPLY=( $( compgen -W "${app_types[*]}" -- ${cur}) )
                    return 0
                    ;;
            esac
        fi

        return 0
    fi

    # Completion of commands and "first level" options.
    if [[ $COMP_CWORD == 1 ]]; then
        COMPREPLY=( $(compgen -W "generate manage -h --help --manual --version" -- "${cur}") )
        return 0
    fi

    # Completion of options and sub-commands.
    cmd="${COMP_WORDS[1]}"

    case $cmd in
        "generate")
            COMPREPLY=( $(compgen -W "system_executable" -- "${cur}") )
            ;;
        "manage"|"stats")
            COMPREPLY=( $(compgen -W "-i --id= -t --type= -f --force-update" -- "${cur}") )
            _decide_nospace_{current_date} ${COMPREPLY[0]}
            ;;
    esac
} &&
complete -F _user_applications_manager_cli_{current_date} {executable_name}
