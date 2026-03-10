import 'package:flutter/material.dart';

class CustomFloatingAppBar extends StatelessWidget {
  final String title;
  final Widget? subtitle;
  final List<Widget>? actions;
  final bool showGradient;
  final Color titleColor;
  final Color iconColor;
  final bool showBack;

  const CustomFloatingAppBar({
    super.key,
    required this.title,
    this.subtitle,
    this.actions,
    this.showGradient = true,
    this.titleColor = Colors.white,
    this.iconColor = Colors.black87,
    this.showBack = false,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: EdgeInsets.only(
        top: MediaQuery.of(context).padding.top + 10,
        left: 16,
        right: 16,
        bottom: 10,
      ),
      decoration: showGradient
          ? BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [
                  Colors.black.withOpacity(0.7),
                  Colors.transparent,
                ],
              ),
            )
          : null,
      child: Row(
        children: [
          // Menu / Back Button
          Builder(
            builder: (context) => Container(
              decoration: BoxDecoration(
                color: Colors.white,
                shape: BoxShape.circle,
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withOpacity(0.2),
                    blurRadius: 8,
                    offset: const Offset(0, 2),
                  ),
                ],
              ),
              child: IconButton(
                icon: Icon(
                  showBack ? Icons.arrow_back : Icons.menu,
                  color: iconColor,
                ),
                onPressed: () {
                  if (showBack) {
                    Navigator.of(context).pop();
                  } else {
                    Scaffold.of(context).openDrawer();
                  }
                },
              ),
            ),
          ),
          const SizedBox(width: 16),

          // Title
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  title.toUpperCase(),
                  style: TextStyle(
                    color: titleColor.withOpacity(0.8),
                    fontSize: 12,
                    fontWeight: FontWeight.bold,
                    letterSpacing: 1.2,
                  ),
                ),
                if (subtitle != null) subtitle!,
              ],
            ),
          ),

          // Actions
          if (actions != null) ...actions!,
        ],
      ),
    );
  }
}
