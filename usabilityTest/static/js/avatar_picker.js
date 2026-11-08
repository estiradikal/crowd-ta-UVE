// Selector de avatar (DiceBear) o foto propia, usado en el registro y en Configuración.
//   opts.grid, opts.hidden, opts.fileInput, opts.preview, opts.shuffle: elementos del DOM
//   opts.keepCurrent: si es true no elige un avatar al azar al cargar (conserva la imagen actual)
//   opts.onChange: se llama cuando el usuario elige otro avatar o sube una foto
window.initAvatarPicker = function (opts) {
    var STYLES = ['adventurer', 'avataaars', 'lorelei', 'notionists', 'personas', 'bottts', 'fun-emoji', 'thumbs'];
    var grid = opts.grid, hidden = opts.hidden, fileInput = opts.fileInput, preview = opts.preview;

    function randomAvatar() {
        var style = STYLES[Math.floor(Math.random() * STYLES.length)];
        var seed = Math.random().toString(36).slice(2, 10);
        return 'https://api.dicebear.com/9.x/' + style + '/svg?seed=' + seed;
    }

    function markSelected(url) {
        grid.querySelectorAll('button').forEach(function (b) {
            b.setAttribute('aria-checked', b.dataset.url === url ? 'true' : 'false');
        });
    }

    function changed() { if (opts.onChange) opts.onChange(); }

    function selectAvatar(url) {
        hidden.value = url;
        fileInput.value = '';
        preview.src = url;
        markSelected(url);
    }

    function fillGrid(keep) {
        grid.innerHTML = '';
        var urls = keep ? [keep] : [];
        while (urls.length < 6) urls.push(randomAvatar());
        urls.forEach(function (url) {
            var b = document.createElement('button');
            b.type = 'button';
            b.className = 'avatar-option';
            b.dataset.url = url;
            b.setAttribute('role', 'radio');
            b.setAttribute('aria-label', 'Avatar');
            b.innerHTML = '<img src="' + url + '" alt="" loading="lazy">';
            b.addEventListener('click', function () { selectAvatar(url); changed(); });
            grid.appendChild(b);
        });
    }

    opts.shuffle.addEventListener('click', function () {
        fillGrid();
        selectAvatar(grid.firstChild.dataset.url);
        changed();
    });

    fileInput.addEventListener('change', function () {
        var file = fileInput.files[0];
        if (!file) return;
        hidden.value = '';
        markSelected(null);
        var reader = new FileReader();
        reader.onload = function (e) { preview.src = e.target.result; };
        reader.readAsDataURL(file);
        changed();
    });

    var initial = hidden.value;
    fillGrid(initial || null);
    if (initial) {
        selectAvatar(initial);
    } else if (!opts.keepCurrent) {
        selectAvatar(grid.firstChild.dataset.url);
    }
};
