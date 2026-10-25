[English](THIRD-PARTY.en.md) | [简体中文](THIRD-PARTY.md) | **Русский**

<a id="第三方来源与授权范围"></a>
<a id="third-party-sources-and-licensing-scope"></a>
# Сторонние источники и области действия лицензий

Эта страница — указатель авторства и источников. Полные лицензии, заголовки авторского права и файлы NOTICE находятся в соответствующих каталогах; это руководство их не заменяет.

| Компонент | Источник / лицензия | Расположение в комплекте |
| --- | --- | --- |
| Рабочее пространство Rust-прошивки Microduck и upstream-код | Pollen Robotics; Apache-2.0 | `firmware/LICENSE`, `firmware/Cargo.toml` |
| Официальный движок обучения | Pollen Robotics microduck_rl; ПО Apache-2.0; при первой подготовке скачивается по коммиту | `training-console/NOTICE.md`, `training-console/docs/licenses/microduck_rl-Apache-2.0.txt` |
| Параметры HD1910 и соответствующая реализация исполнительного механизма | fanhao 375/microduck-replica; соответствующий код Apache-2.0 | `training-console/docs/licenses/`, `training/hd1910_m6.json`, `training/hd1910_actuator.py` (последние два внутри training-console) |
| Three.js | Авторы Three.js; MIT | `firmware/console/licenses/THREE-MIT.txt` |
| ONNX Runtime 1.28.0 | Microsoft и авторы зависимостей; MIT и перечисленные сторонние условия | `firmware/packaging/onnxruntime/LICENSE`, `ThirdPartyNotices.txt` |
| PyYAML | Исходные авторы; MIT | `firmware/packaging/_model_yaml/LICENSE` |
| tomli | Taneli Hukkinen; MIT | `training-console/training/_vendor/tomli/LICENSE` |
| Драйверы IMU и ToF ST | STMicroelectronics; соответствующие заголовки и прилагаемые условия BSD | `firmware/firmware/imu-source/vendor/lsm6dsv16x/LICENSE`, `firmware/tof/vendor/LICENSE.txt` |
| Официальная геометрия и отображаемые сетки | Pollen Robotics и авторы моделей; upstream README указывает Creative Commons BY-SA-NC без версии | `firmware/console/licenses/MODEL-NOTICE.md` |
| Официальные эталонные ONNX и модели обнаружения | Соответствующие upstream-лицензии моделей; личные условия автора не применяются | `firmware/verification/official-reference/`, `firmware/pet-detect/` |
| Пять текущих политик, обученных автором | Личные условия относятся только к весам и записям, на которые автор вправе выдавать лицензию; upstream-права сохраняются | `firmware/policies/`, `firmware/BUILD.json` |

Upstream-прошивка остаётся под Apache-2.0 со всеми предусмотренными разрешениями. Нельзя объявить весь сторонний код, модели и геометрию доступными «только для личного использования». Корневая LICENSE определяет область личного некоммерческого использования авторских консолей и новых опубликованных материалов.

В декларации официальной геометрии версия лицензии не указана. Комплект сохраняет требования указания авторства, некоммерческого использования и распространения производных на тех же условиях, не придумывая версию 4.0 и не заменяя лицензию геометрии лицензией ПО.

ZIP-архивы скомпилированной прошивки используют те же лицензии компонентов: программы прошивки Apache, отдельно лицензируемые библиотеки / ресурсы и самостоятельно обученные модели, на которые автор вправе выдавать лицензию. Приложенные личные условия не меняют лицензию программ Apache.

<a id="上游链接"></a>
<a id="upstream-links"></a>
## Ссылки на upstream

- [Microduck](https://github.com/pollen-robotics/microduck)
- [microduck_rl](https://github.com/pollen-robotics/microduck_rl)
- [microduck-replica](https://github.com/fanhao375/microduck-replica)
- [Исходный текст Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0)
- [Определение OSI](https://opensource.org/osd)

Товарные знаки Microduck, Pollen Robotics и третьих сторон принадлежат своим владельцам. Проект не подразумевает официального одобрения.
