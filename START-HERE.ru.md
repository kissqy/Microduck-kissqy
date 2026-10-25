[English](START-HERE.en.md) | [Оригинал](START-HERE.txt) | **Русский**

<a id="current-public-microduck-release"></a>
# Текущий опубликованный выпуск Microduck

Проект: <https://github.com/kissqy/Microduck-kissqy>

На главной странице находятся образ системы, ZIP-архивы двух консолей и ссылки на исходники.

- Robot Console: R17 V167 (1.0.167)
- Прошивка робота: официальная 0.15.1 / control.43 / API40
- Training Studio: R1.5.27
- Образ системы: Public Image R1; настройка Wi-Fi при первом запуске R5

Расположение исходников:

- Прошивка: `microduck-hd1910/firmware/`
- Robot Console: `microduck-hd1910/firmware/console/`
- Training Studio: `microduck-hd1910/training-console/`
- Готовые ZIP-архивы: каталог `release-assets/` в корне
- Образ системы: выпуск `public-image-r1`

V167 используется вместе с control.43. Изменение: исправлено дрожание корпуса.

Перед первым движением проверьте калибровку именно своего робота и соблюдайте порядок HOME → hold → walk: возврат в исходное положение, удержание, ходьба. Лицензирование компонентов описано в `microduck-hd1910/LICENSE`; сторонние материалы сохраняют исходные условия.

В образе R1 по-прежнему находится control.40; установите прошивку из комплекта V167 для обновления до control.43.
