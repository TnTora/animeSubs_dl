local utils = require('mp.utils')
local script_path = utils.join_path(mp.get_script_directory(), "subs-dl.py")
local custom_python_cmd = ""
local running = false
local script_run

if package.config:sub(1,1) == '/' then
    python_cmd = "python3"
    new_ipc_server = "/tmp/mpvsocket"
else
    python_cmd = "py"
    new_ipc_server = "\\\\.\\pipe\\tmp\\mpvsocket"
end

if custom_python_cmd then
    python_cmd = custom_python_cmd
end

function down_subs()
    if running then
        mp.abort_async_command(script_run)
    end
    running = true
    mp.msg.warn('Searching...')
    mp.command('show-text "Searching..."')

    local old_ipc_server = mp.get_property_native("input-ipc-server")
    if old_ipc_server == "" then
        mp.set_property("input-ipc-server", new_ipc_server)
    else
        new_ipc_server = old_ipc_server
    end

    local arguments = {
        python_cmd,
        script_path,
        new_ipc_server,
    }

    script_run = mp.command_native_async({
        name = "subprocess",
        playback_only = true,
        capture_stdout = false,
        args = arguments,
    },
    function(res, val, err)
        mp.set_property("input-ipc-server", old_ipc_server)
        running = false
    end
    )

end;

mp.add_key_binding("Ctrl+K", "auto_download_subs", down_subs, {repeatable=true})

