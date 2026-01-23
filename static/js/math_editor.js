document.addEventListener('DOMContentLoaded', function() {
    const templateType = document.getElementById('templateType');
    const templateParams = document.getElementById('templateParams');
    const taskEditor = document.getElementById('taskEditor');
    const mathPreview = document.getElementById('mathPreview');
    
    // Загрузка шаблонов при выборе типа
    templateType.addEventListener('change', function() {
        if (this.value === 'custom') {
            templateParams.classList.add('hidden');
            taskEditor.value = '';
            updatePreview();
            return;
        }
        
        fetch(`/get_math_templates?type=${this.value}`)
            .then(response => response.json())
            .then(templates => {
                renderTemplateParams(templates[0]); // Берем первый подходящий шаблон
            });
    });
    
    // Кнопки математического редактора
    document.querySelectorAll('.btn-math').forEach(btn => {
        btn.addEventListener('click', function() {
            insertAtCursor(taskEditor, this.dataset.insert);
        });
    });
    
    // Обновление превью при изменении
    taskEditor.addEventListener('input', updatePreview);
    
    function renderTemplateParams(template) {
        templateParams.innerHTML = '';
        const params = JSON.parse(template.parameters);
        
        for (const [param, config] of Object.entries(params)) {
            const paramDiv = document.createElement('div');
            paramDiv.className = 'param-group';
            
            const label = document.createElement('label');
            label.textContent = `Параметр ${param}:`;
            
            let input;
            if (config.type === 'int' || config.type === 'float') {
                input = document.createElement('input');
                input.type = 'number';
                input.step = config.step || 1;
                input.min = config.min;
                input.max = config.max;
                input.value = config.default || config.min;
                input.className = 'param-input';
                input.dataset.param = param;
            } else if (config.type === 'choice') {
                input = document.createElement('select');
                input.className = 'param-select';
                input.dataset.param = param;
                config.values.forEach(value => {
                    const option = document.createElement('option');
                    option.value = value;
                    option.textContent = value;
                    input.appendChild(option);
                });
            }
            
            paramDiv.appendChild(label);
            paramDiv.appendChild(input);
            templateParams.appendChild(paramDiv);
        }
        
        templateParams.classList.remove('hidden');
        taskEditor.value = template.template;
        updatePreview();
    }
    
    function insertAtCursor(field, value) {
        const startPos = field.selectionStart;
        const endPos = field.selectionEnd;
        const cursorPos = startPos;
        const beforeText = field.value.substring(0, startPos);
        const afterText = field.value.substring(endPos, field.value.length);
        
        field.value = beforeText + value + afterText;
        field.selectionStart = cursorPos + value.indexOf('}') + 1;
        field.selectionEnd = field.selectionStart;
        field.focus();
        
        updatePreview();
    }
    
    function updatePreview() {
        // Здесь можно подключить библиотеку MathJax или KaTeX для рендеринга
        mathPreview.textContent = taskEditor.value;
    }
});