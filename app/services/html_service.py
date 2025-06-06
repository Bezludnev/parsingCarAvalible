# app/services/html_service.py - ОБНОВЛЕННАЯ с поддержкой описаний
import os
from datetime import datetime
from typing import Dict, Any, List
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class HTMLReportService:
    def __init__(self):
        self.reports_dir = Path("reports")
        self.reports_dir.mkdir(exist_ok=True)

    def generate_analysis_report(self, analysis_result: Dict[str, Any]) -> str:
        """Генерирует HTML отчет с AI анализом"""

        report_name = self._generate_report_name(analysis_result)
        file_path = self.reports_dir / f"{report_name}.html"

        html_content = self._build_html_content(analysis_result)

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(html_content)

            logger.info(f"✅ HTML отчет создан: {file_path}")
            return str(file_path)

        except Exception as e:
            logger.error(f"❌ Ошибка создания HTML отчета: {e}")
            raise

    def _generate_report_name(self, analysis_result: Dict[str, Any]) -> str:
        """Генерирует имя файла отчета"""

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Определяем тип анализа для имени
        analysis_type = analysis_result.get("analysis_type", "unknown")
        filter_name = analysis_result.get("filter_name", "")
        brand = analysis_result.get("brand", "")
        total_cars = analysis_result.get("total_cars_analyzed", 0)

        if analysis_type == "full_database":
            return f"ai_full_market_{total_cars}cars_{timestamp}"
        elif analysis_type == "market_trends":
            days = analysis_result.get("trends_period_days", 14)
            return f"ai_market_trends_{days}days_{total_cars}cars_{timestamp}"
        elif filter_name:
            return f"ai_analysis_{filter_name}_{total_cars}cars_{timestamp}"
        elif brand:
            return f"ai_analysis_{brand}_{total_cars}cars_{timestamp}"
        elif analysis_type == "recent_cars":
            days = analysis_result.get("days_period", 7)
            return f"ai_analysis_recent_{days}days_{total_cars}cars_{timestamp}"
        elif analysis_type == "comparison":
            car_ids = analysis_result.get("compared_car_ids", [])
            return f"ai_comparison_{len(car_ids)}cars_{timestamp}"
        else:
            return f"ai_analysis_{analysis_type}_{total_cars}cars_{timestamp}"

    def _build_html_content(self, analysis_result: Dict[str, Any]) -> str:
        """Строит HTML контент отчета"""

        # Извлекаем данные
        total_cars = analysis_result.get("total_cars_analyzed", 0)
        analysis_type = analysis_result.get("analysis_type", "unknown")
        model_used = analysis_result.get("model_used", "AI")

        # Определяем какие поля использовать в зависимости от типа анализа
        if analysis_type == "full_database":
            top_recommendations = analysis_result.get("top_recommendations", "")
            detailed_analysis = analysis_result.get("brand_analysis", "")
            general_conclusions = analysis_result.get("general_conclusions", "")
            market_overview = analysis_result.get("market_overview", "")
        elif analysis_type == "market_trends":
            top_recommendations = analysis_result.get("market_dynamics", "")
            detailed_analysis = analysis_result.get("price_trends", "")
            general_conclusions = analysis_result.get("conclusions", "")
            market_overview = analysis_result.get("forecast", "")
        else:
            # Legacy format
            top_recommendations = analysis_result.get("top_recommendations", "")
            detailed_analysis = analysis_result.get("detailed_analysis", "")
            general_conclusions = analysis_result.get("general_conclusions", "")
            market_overview = ""

        full_analysis = analysis_result.get("full_analysis", "")
        cars_data = analysis_result.get("cars_data", [])
        recommended_ids = analysis_result.get("recommended_car_ids", [])

        # Определяем заголовок
        title = self._get_analysis_title(analysis_result)

        return f"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 30px;
        }}
        .header h1 {{
            margin: 0;
            font-size: 2.2em;
        }}
        .meta-info {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 30px;
        }}
        .meta-card {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            border-left: 4px solid #667eea;
        }}
        .section {{
            margin-bottom: 40px;
        }}
        .section h2 {{
            color: #2c3e50;
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
            font-size: 1.5em;
        }}
        .recommendations {{
            background: #e8f5e8;
            padding: 20px;
            border-radius: 8px;
            border-left: 5px solid #27ae60;
        }}
        .detailed-analysis {{
            background: #fff3cd;
            padding: 20px;
            border-radius: 8px;
            border-left: 5px solid #ffc107;
        }}
        .conclusions {{
            background: #d1ecf1;
            padding: 20px;
            border-radius: 8px;
            border-left: 5px solid #17a2b8;
        }}
        .market-overview {{
            background: #f8d7da;
            padding: 20px;
            border-radius: 8px;
            border-left: 5px solid #dc3545;
        }}
        .cars-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
            font-size: 0.9em;
        }}
        .table-responsive {{
            overflow-x: auto;
        }}
        .cars-table th, .cars-table td {{
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
            vertical-align: top;
        }}
        .cars-table th {{
            background-color: #f2f2f2;
            font-weight: bold;
            position: sticky;
            top: 0;
        }}
        .recommended-car {{
            background-color: #d4edda !important;
        }}
        .car-link {{
            color: #007bff;
            text-decoration: none;
        }}
        .car-link:hover {{
            text-decoration: underline;
        }}
        .description-cell {{
            max-width: 200px;
            word-wrap: break-word;
            font-size: 0.8em;
            color: #666;
        }}
        .footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            color: #666;
            font-size: 0.9em;
        }}
        .full-analysis {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            white-space: pre-wrap;
            font-family: monospace;
            font-size: 0.9em;
            max-height: 500px;
            overflow-y: auto;
        }}
        .analysis-text {{
            white-space: pre-wrap;
            line-height: 1.5;
        }}
        @media (max-width: 600px) {{
            .meta-info {{
                grid-template-columns: 1fr;
            }}
            .cars-table th, .cars-table td {{
                padding: 6px;
                font-size: 0.8em;
            }}
            .description-cell {{
                max-width: 150px;
                font-size: 0.75em;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 {title}</h1>
            <p>Полный AI анализ автомобилей с описаниями • {datetime.now().strftime("%d.%m.%Y %H:%M")}</p>
        </div>

        <div class="meta-info">
            <div class="meta-card">
                <strong>📊 Проанализировано машин:</strong><br>
                {total_cars}
            </div>
            <div class="meta-card">
                <strong>🤖 AI Модель:</strong><br>
                {model_used}
            </div>
            <div class="meta-card">
                <strong>📋 Тип анализа:</strong><br>
                {self._format_analysis_type(analysis_result)}
            </div>
            <div class="meta-card">
                <strong>⭐ Рекомендованных:</strong><br>
                {len(recommended_ids)} из {total_cars}
            </div>
        </div>

        {self._format_section("📊 ОБЗОР РЫНКА", market_overview, "market-overview") if market_overview else ""}

        {self._format_section("🏆 ТОП РЕКОМЕНДАЦИИ", top_recommendations, "recommendations") if top_recommendations else ""}

        {self._format_section("📝 ДЕТАЛЬНЫЙ АНАЛИЗ", detailed_analysis, "detailed-analysis") if detailed_analysis else ""}

        {self._format_section("📊 ОБЩИЕ ВЫВОДЫ", general_conclusions, "conclusions") if general_conclusions else ""}

        <div class="section">
            <h2>📋 Список проанализированных автомобилей</h2>
            <div class="table-responsive">
            <table class="cars-table">
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Название</th>
                        <th>Марка</th>
                        <th>Год</th>
                        <th>Цена</th>
                        <th>Пробег</th>
                        <th>Рекомендован</th>
                        <th>Описание</th>
                        <th>Ссылка</th>
                    </tr>
                </thead>
                <tbody>
                    {self._generate_cars_table_rows(cars_data, recommended_ids)}
                </tbody>
            </table>
            </div>
        </div>

        {self._format_full_analysis_section(full_analysis) if full_analysis else ""}

        <div class="footer">
            <p>
                <strong>Отчет создан:</strong> {datetime.now().strftime("%d %B %Y в %H:%M")} |
                <strong>Система:</strong> Car Monitor Bot v2.1 |
                <strong>AI:</strong> {model_used} |
                <strong>📝 Описания:</strong> включены в анализ
            </p>
        </div>
    </div>
</body>
</html>
"""

    def _get_analysis_title(self, analysis_result: Dict[str, Any]) -> str:
        """Генерирует заголовок для отчета"""

        analysis_type = analysis_result.get("analysis_type", "")
        filter_name = analysis_result.get("filter_name", "")
        brand = analysis_result.get("brand", "")

        if analysis_type == "full_database":
            return "Полный анализ рынка"
        elif analysis_type == "market_trends":
            days = analysis_result.get("trends_period_days", 14)
            return f"Анализ трендов за {days} дней"
        elif filter_name:
            return f"Анализ {filter_name.title()}"
        elif brand:
            return f"Анализ марки {brand.title()}"
        elif analysis_type == "recent_cars":
            days = analysis_result.get("days_period", 7)
            return f"Анализ поступлений за {days} дней"
        elif analysis_type == "comparison":
            return "Сравнение выбранных автомобилей"
        else:
            return "AI Анализ автомобилей"

    def _format_analysis_type(self, analysis_result: Dict[str, Any]) -> str:
        """Форматирует тип анализа для отображения"""

        analysis_type = analysis_result.get("analysis_type", "unknown")
        filter_name = analysis_result.get("filter_name", "")
        brand = analysis_result.get("brand", "")

        if analysis_type == "full_database":
            brands_count = len(analysis_result.get("brands_analyzed", []))
            return f"Полный рынок ({brands_count} брендов)"
        elif analysis_type == "market_trends":
            days = analysis_result.get("trends_period_days", 14)
            return f"Тренды за {days} дней"
        elif filter_name:
            return f"По фильтру: {filter_name}"
        elif brand:
            return f"По марке: {brand}"
        elif analysis_type == "recent_cars":
            days = analysis_result.get("days_period", 7)
            return f"Поступления за {days} дней"
        elif analysis_type == "comparison":
            return "Сравнение машин"
        else:
            return analysis_type

    def _format_section(self, title: str, content: str, css_class: str) -> str:
        """Форматирует секцию отчета"""

        if not content:
            return ""

        return f"""
        <div class="section">
            <h2>{title}</h2>
            <div class="{css_class}">
                <div class="analysis-text">{content}</div>
            </div>
        </div>
        """

    def _generate_cars_table_rows(self, cars_data: List[Dict], recommended_ids: List[int]) -> str:
        """Генерирует строки таблицы с машинами (включая описания)"""

        if not cars_data:
            return "<tr><td colspan='9'>Нет данных о машинах</td></tr>"

        rows = []
        for car in cars_data:
            car_id = car.get("id", "N/A")
            is_recommended = car_id in recommended_ids
            row_class = "recommended-car" if is_recommended else ""

            title = car.get("title", "N/A")[:40] + ("..." if len(car.get("title", "")) > 40 else "")

            # Обрабатываем описание для таблицы
            description = car.get("description", "")
            if description:
                desc_short = description[:120] + ("..." if len(description) > 120 else "")
            else:
                desc_short = "нет описания"

            row = f"""
                <tr class="{row_class}">
                    <td>{car_id}</td>
                    <td>{title}</td>
                    <td>{car.get("brand", "N/A")}</td>
                    <td>{car.get("year", "N/A")}</td>
                    <td>{car.get("price", "N/A")}</td>
                    <td>{f"{car.get('mileage', 0):,} км" if car.get("mileage") else "N/A"}</td>
                    <td>{"✅ Да" if is_recommended else "❌ Нет"}</td>
                    <td class="description-cell">{desc_short}</td>
                    <td><a href="{car.get('link', '#')}" class="car-link" target="_blank">Открыть</a></td>
                </tr>
            """
            rows.append(row)

        return "".join(rows)

    def _format_full_analysis_section(self, full_analysis: str) -> str:
        """Форматирует секцию с полным анализом"""

        if not full_analysis:
            return ""

        return f"""
        <div class="section">
            <h2>📄 Полный текст AI анализа</h2>
            <div class="full-analysis">
{full_analysis}
            </div>
        </div>
        """

    def get_reports_list(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Возвращает список последних отчетов"""

        try:
            reports = []

            for file_path in sorted(self.reports_dir.glob("*.html"),
                                    key=lambda x: x.stat().st_mtime, reverse=True)[:limit]:
                stat = file_path.stat()
                reports.append({
                    "filename": file_path.name,
                    "size_mb": round(stat.st_size / 1024 / 1024, 2),
                    "created": datetime.fromtimestamp(stat.st_mtime).strftime("%d.%m.%Y %H:%M"),
                    "path": str(file_path)
                })

            return reports

        except Exception as e:
            logger.error(f"Ошибка получения списка отчетов: {e}")
            return []

    def clean_old_reports(self, keep_days: int = 7):
        """Удаляет старые отчеты"""

        try:
            cutoff_time = datetime.now().timestamp() - (keep_days * 24 * 3600)
            deleted_count = 0

            for file_path in self.reports_dir.glob("*.html"):
                if file_path.stat().st_mtime < cutoff_time:
                    file_path.unlink()
                    deleted_count += 1

            logger.info(f"Удалено {deleted_count} старых отчетов (старше {keep_days} дней)")
            return deleted_count

        except Exception as e:
            logger.error(f"Ошибка очистки старых отчетов: {e}")
            return 0