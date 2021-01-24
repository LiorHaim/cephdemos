SELECT "songname" AS "songname",
       count(*) AS "count"
FROM
  (SELECT *
   FROM songs.songs) AS "expr_qry"
GROUP BY "songname"
ORDER BY "count" DESC
LIMIT 1000;
