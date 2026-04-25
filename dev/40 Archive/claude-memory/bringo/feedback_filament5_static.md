---
name: Filament 5 non-static properties
description: В Filament 5 свойства $view, $layout, $navigationIcon стали non-static — при создании страниц/виджетов/ресурсов использовать protected (не protected static)
type: feedback
---

В Filament 5 (api/ субмодуль) несколько свойств изменили сигнатуру:
- `$view` в Pages и Widgets — теперь `protected string $view` (НЕ `protected static string $view`)
- `$layout` в Pages — теперь `protected string $layout` (НЕ static)
- `$navigationIcon` в Resources — теперь `protected static string|\BackedEnum|null $navigationIcon` (НЕ `?string`)

**Why:** Filament 5 изменил архитектуру, FatalError при несовпадении типов.
**How to apply:** При создании любых Filament компонентов (Pages, Widgets, Resources) в api/ субмодуле сверять с существующими файлами (ClientResource, AdminPanelProvider) для точных сигнатур.
