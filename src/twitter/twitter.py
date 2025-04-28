from dataclasses import dataclass
import sys
from pathlib import Path
import asyncio
import json
from typing import Dict, Optional, List
import aiohttp
from datetime import datetime
import os

from src.helpers.headerManager import HeaderManager
from src.helpers.proxyManager import ProxyManager
from .models import TweetAnalysisResult, TwitterUser, TwitterResponse


class NoHeadersAvailableError(Exception):
    """Исключение, возникающее, когда закончились доступные заголовки."""
    pass


class TwitterService:
    def __init__(self):
        self.proxy_manager = ProxyManager()
        self.header_manager = HeaderManager()

    async def _make_request(self, url: str, headers: Optional[Dict[str, str]] = None) -> Optional[Dict]:
        current_retry = 0
        delay = 1

        headers = None
        while current_retry < 4:
            headers = self.header_manager.get_next_header()
            if headers is None:
                print("❌ Нет доступных заголовков")
                raise NoHeadersAvailableError("Закончились доступные заголовки для запросов")
            try:
                print(
                    f"Попытка {current_retry + 1}/4 - "
                    f"Отправка запроса к Twitter API"
                )

                try:
                    connector = aiohttp.TCPConnector(ssl=False)
                    timeout = aiohttp.ClientTimeout(
                        total=30,
                        connect=10,
                        sock_read=10
                    )

                    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                        def twitter_status_check(status):
                            nonlocal headers
                            if status == 200:
                                return True
                            if status == 401:
                                self.header_manager.mark_header_failed(headers)
                                print("Получен статус 401 (Unauthorized) - меняем заголовок")
                                headers = self.header_manager.get_next_header()
                                if headers is None:
                                    print("❌ Нет доступных заголовков для продолжения")
                                    raise NoHeadersAvailableError("Закончились доступные заголовки после 401")
                                return False
                            if status in [429, 500, 502, 503, 504]:
                                print(f"Получен статус {status} - меняем прокси и пробуем снова")
                                return False
                            return False

                        try:
                            result = await self.proxy_manager.execute_with_proxy_rotation(
                                session=session,
                                url=url,
                                method="GET",
                                headers=headers,
                                status_check=twitter_status_check
                            )

                            if result:
                                return result
                            else:
                                current_retry += 1
                                continue

                        except Exception as proxy_error:
                            pass

                except asyncio.CancelledError:
                    print("Соединение было отменено - пробуем следующую попытку")
                    current_retry += 1
                    continue

                except asyncio.TimeoutError:
                    print("Таймаут соединения - пробуем следующую попытку")
                    current_retry += 1
                    continue

            except Exception as e:
                print(
                    f"❌ Ошибка при попытке {current_retry + 1}/4:\n"
                    f"Тип ошибки: {type(e).__name__}\n"
                    f"Детали: {str(e)}"
                )
                current_retry += 1

            if current_retry < 4:
                print(f"Ожидание {delay} секунд перед следующей попыткой")
                await asyncio.sleep(delay)
                delay *= 1

        return None

    async def get_tweets(self, query: str) -> Optional[Dict]:
        url = f"https://x.com/i/api/graphql/KI9jCXUx3Ymt-hDKLOZb9Q/SearchTimeline?variables=%7B%22rawQuery%22%3A%22{query}%22%2C%22count%22%3A20%2C%22querySource%22%3A%22typed_query%22%2C%22product%22%3A%22Latest%22%7D&features=%7B%22profile_label_improvements_pcf_label_in_post_enabled%22%3Atrue%2C%22rweb_tipjar_consumption_enabled%22%3Atrue%2C%22responsive_web_graphql_exclude_directive_enabled%22%3Atrue%2C%22verified_phone_label_enabled%22%3Afalse%2C%22creator_subscriptions_tweet_preview_api_enabled%22%3Atrue%2C%22responsive_web_graphql_timeline_navigation_enabled%22%3Atrue%2C%22responsive_web_graphql_skip_user_profile_image_extensions_enabled%22%3Afalse%2C%22premium_content_api_read_enabled%22%3Afalse%2C%22communities_web_enable_tweet_community_results_fetch%22%3Atrue%2C%22c9s_tweet_anatomy_moderator_badge_enabled%22%3Atrue%2C%22responsive_web_grok_analyze_button_fetch_trends_enabled%22%3Afalse%2C%22responsive_web_grok_analyze_post_followups_enabled%22%3Atrue%2C%22responsive_web_jetfuel_frame%22%3Afalse%2C%22responsive_web_grok_share_attachment_enabled%22%3Atrue%2C%22articles_preview_enabled%22%3Atrue%2C%22responsive_web_edit_tweet_api_enabled%22%3Atrue%2C%22graphql_is_translatable_rweb_tweet_is_translatable_enabled%22%3Atrue%2C%22view_counts_everywhere_api_enabled%22%3Atrue%2C%22longform_notetweets_consumption_enabled%22%3Atrue%2C%22responsive_web_twitter_article_tweet_consumption_enabled%22%3Atrue%2C%22tweet_awards_web_tipping_enabled%22%3Afalse%2C%22creator_subscriptions_quote_tweet_preview_enabled%22%3Afalse%2C%22freedom_of_speech_not_reach_fetch_enabled%22%3Atrue%2C%22standardized_nudges_misinfo%22%3Atrue%2C%22tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled%22%3Atrue%2C%22rweb_video_timestamps_enabled%22%3Atrue%2C%22longform_notetweets_rich_text_read_enabled%22%3Atrue%2C%22longform_notetweets_inline_media_enabled%22%3Atrue%2C%22responsive_web_grok_image_annotation_enabled%22%3Atrue%2C%22responsive_web_enhance_cards_enabled%22%3Afalse%7D"

        return await self._make_request(url)

    @staticmethod
    def _create_twitter_user(username: str, user_data: Dict) -> TwitterUser:
        return TwitterUser(
            username=username,
            is_dm_open=user_data.get('is_dm_open', False),
            followers_count=user_data.get('followers_count', 0),
            tweets_count=user_data.get('tweets_count', 0)
        )

    def _analyze_user_activity(self, users: Dict[str, TwitterUser]) -> TweetAnalysisResult:
        total_tweets = sum(user.tweets_count for user in users.values())
        unique_users = len(users)

        if total_tweets == 0:
            return None

        if total_tweets <= 3:
            return self._analyze_low_activity(users, total_tweets, unique_users)
        return self._analyze_high_activity(users, total_tweets, unique_users)

    def _analyze_low_activity(
            self,
            users: Dict[str, TwitterUser],
            total_tweets: int,
            unique_users: int
    ) -> TweetAnalysisResult:
        selected_user = None
        status = "YELLOW"

        if total_tweets == 1:
            selected_user = next(iter(users.keys()))
        elif total_tweets == 2 and unique_users == 1:
            status = "GREEN"
            selected_user = next(iter(users.keys()))
        elif unique_users == 1:
            status = "GREEN"
            selected_user = next(iter(users.keys()))
        elif unique_users == 3:
            status = "RED"
        else:
            selected_user = max(users.items(), key=lambda x: x[1].tweets_count)[0]

        return TweetAnalysisResult(
            status=status,
            selected_user=selected_user,
            user_data=users[selected_user].__dict__ if selected_user else None,
            total_tweets=total_tweets,
            unique_users=unique_users
        )

    def _analyze_high_activity(
            self,
            users: Dict[str, TwitterUser],
            total_tweets: int,
            unique_users: int
    ) -> TweetAnalysisResult:
        if unique_users == total_tweets:
            status = "RED"
            selected_user = None
        else:
            status = "GREEN" if unique_users == 1 else "YELLOW"
            selected_user = max(users.items(), key=lambda x: x[1].tweets_count)[0]

        return TweetAnalysisResult(
            status=status,
            selected_user=selected_user,
            user_data=users[selected_user].__dict__ if selected_user else None,
            total_tweets=total_tweets,
            unique_users=unique_users
        )

    def _print_analysis_results(self, result: TweetAnalysisResult) -> None:
        print("---------------------")
        print("РЕЗУЛЬТАТЫ АНАЛИЗА ТВИТОВ")
        print("---------------------")

        print(
            f"Всего твитов: {result.total_tweets}, "
            f"Уникальных пользователей: {result.unique_users}"
        )

        if result.selected_user:
            print("---------------------")
            print(f"Выбранный пользователь: {result.selected_user}")
            if result.user_data:
                print(
                    f"Подписчиков: {result.user_data['followers_count']:,}, "
                    f"DM {'открыты' if result.user_data['is_dm_open'] else 'закрыты'}"
                )

        print("---------------------")
        status_colors = {
            "GREEN": 'green',
            "YELLOW": 'yellow',
            "RED": 'red'
        }

        if result.status in status_colors:
            color = status_colors[result.status]
            print(f"Статус анализа: {result.status}")

        print("---------------------")

    async def analyze_tweets(self, query_id: str) -> Optional[TweetAnalysisResult]:
        print(f"Начало анализа твитов для запроса: {query_id}")

        users: Dict[str, TwitterUser] = {}
        processed_tweets = 0

        try:
            # Получение твитов
            tweets = await self.get_tweets(query_id)
            if not tweets:
                print("Твиты не найдены")
                return self._analyze_user_activity(users)

            # Извлечение записей
            try:
                entries = tweets['data']['search_by_raw_query']['search_timeline']['timeline']['instructions'][0][
                    'entries']
                print(f"Получено {len(entries)} записей для анализа")
            except (KeyError, IndexError) as e:
                print(f"❌ Ошибка при разборе данных: {str(e)}")
                return self._analyze_user_activity(users)

            # Обработка твитов
            for entry in entries:
                try:
                    if entry['entryId'].startswith('cursor-top'):
                        continue

                    result = entry['content']['itemContent']['tweet_results']['result']
                    core = result['core']
                    core_result = core['user_results']['result']
                    if core_result['legacy']['followers_count'] <= int(os.getenv("MIN_FOLLOWERS")):
                        continue

                    username = core_result['legacy']['screen_name']
                    if username not in users:
                        users[username] = self._create_twitter_user(
                            username=username,
                            user_data={
                                'is_dm_open': core_result['legacy']['can_dm'],
                                'followers_count': core_result['legacy']['followers_count'],
                                'tweets_count': 1
                            }
                        )
                    else:
                        users[username].tweets_count += 1

                    processed_tweets += 1

                except (KeyError, TypeError) as e:
                    print(f"❌ Ошибка при обработке твита: {str(e)}")
                    continue

            # Анализ активности пользователей
            result = self._analyze_user_activity(users)
            if result:
                print(
                    f"Анализ завершен\n"
                    f"Статус: {result.status}\n"
                    f"Выбранный пользователь: {result.selected_user}\n"
                    f"Всего твитов: {result.total_tweets}\n"
                    f"Уникальных пользователей: {result.unique_users}"
                )
                self._print_analysis_results(result)
            else:
                print("Анализ не дал результатов")

            return result

        except NoHeadersAvailableError as e:
            print(f"❌ Ошибка: {str(e)}. Возвращаю промежуточные результаты...")
            result = self._analyze_user_activity(users)
            if result:
                print(
                    f"Промежуточный анализ завершен\n"
                    f"Статус: {result.status}\n"
                    f"Выбранный пользователь: {result.selected_user}\n"
                    f"Всего твитов: {result.total_tweets}\n"
                    f"Уникальных пользователей: {result.unique_users}"
                )
                self._print_analysis_results(result)
            else:
                print("Промежуточный анализ не дал результатов")
            return result

        except KeyboardInterrupt:
            print("❌ Процесс прерван пользователем (Ctrl+C). Возвращаю промежуточные результаты...")
            result = self._analyze_user_activity(users)
            if result:
                print(
                    f"Промежуточный анализ завершен\n"
                    f"Статус: {result.status}\n"
                    f"Выбранный пользователь: {result.selected_user}\n"
                    f"Всего твитов: {result.total_tweets}\n"
                    f"Уникальных пользователей: {result.unique_users}"
                )
                self._print_analysis_results(result)
            else:
                print("Промежуточный анализ не дал результатов")
            return result

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            print(f"❌ Сетевая ошибка: {str(e)}. Возвращаю промежуточные результаты...")
            result = self._analyze_user_activity(users)
            if result:
                print(
                    f"Промежуточный анализ завершен\n"
                    f"Статус: {result.status}\n"
                    f"Выбранный пользователь: {result.selected_user}\n"
                    f"Всего твитов: {result.total_tweets}\n"
                    f"Уникальных пользователей: {result.unique_users}"
                )
                self._print_analysis_results(result)
            else:
                print("Промежуточный анализ не дал результатов")
            return result